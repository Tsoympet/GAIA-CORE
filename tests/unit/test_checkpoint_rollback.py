"""Operator rollback restores a verified checkpoint without reviving authority."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gaia.core.runtime import create_runtime
from gaia.core.session import Session
from gaia.kernel.goal_manager import GoalStatus
from gaia.kernel.interrupt_controller import InterruptController
from gaia.kernel.resource_budget import ResourceBudget
from gaia.security.policy import SecurityDecision, SecurityPolicy
from gaia.server.app import create_app


class ApprovalRequiredPolicy(SecurityPolicy):
    """Admit work only after an in-process human approval."""

    def evaluate_objective(self, objective: str) -> SecurityDecision:
        decision = super().evaluate_objective(objective)
        if not decision.allowed:
            return decision
        return SecurityDecision(allowed=True, requires_human_approval=True)


def test_discard_absent_keeps_the_global_latch() -> None:
    controller = InterruptController()
    controller.request("gone", "later goal")
    controller.request("kept", "surviving goal")
    controller.request_global("operator hold")
    controller.discard_absent({"kept"})
    assert controller.pending_count() == 2
    controller.clear_global()
    assert controller.get("gone") is None
    assert controller.get("kept") is not None


@pytest.mark.asyncio
async def test_rollback_drops_live_approvals_and_later_goals(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    runtime.kernel.policy.security_policy = ApprovalRequiredPolicy()
    waiting = await runtime.kernel.run("Draft a local note", "session-rollback")
    assert waiting.goal.status is GoalStatus.WAITING_FOR_USER
    journal = runtime.kernel.continuity
    assert journal is not None
    baseline = next(
        item
        for item in journal.store.list_checkpoints()
        if item.reason == "waiting_for_user"
    )
    runtime.kernel.grant_approval(waiting.goal.id, "operator")
    task = journal.store.get_task_by_goal(waiting.goal.id)
    assert task is not None
    assert journal.approval_is_live(task.task_id, task.action_fingerprint) is True

    runtime.kernel.interrupts.request_global("stop the later goal")
    later = await runtime.kernel.run("A later local note", "session-rollback")
    runtime.kernel.interrupts.clear_global()
    runtime.kernel.interrupts.request(later.goal.id, "pending after the checkpoint")

    restored = runtime.rollback_checkpoint(baseline.checkpoint_id)
    assert restored.reason == "rollback"
    assert restored.parent_checkpoint_id == baseline.checkpoint_id
    assert runtime.kernel.goals.get(later.goal.id) is None
    assert runtime.kernel.store.get_goal(later.goal.id) is None
    assert runtime.kernel.interrupts.get(later.goal.id) is None
    restored_task = journal.store.get_task_by_goal(waiting.goal.id)
    assert restored_task is not None
    assert journal.approval_is_live(
        restored_task.task_id,
        restored_task.action_fingerprint,
    ) is False

    with pytest.raises(RuntimeError, match="no live in-process approval"):
        await runtime.kernel.resume(waiting.goal.id)

    runtime.kernel.grant_approval(waiting.goal.id, "operator")
    resumed = await runtime.kernel.resume(waiting.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED


@pytest.mark.asyncio
async def test_rollback_keeps_a_surviving_budget_and_reports_its_limits(
    tmp_path: Path,
) -> None:
    runtime = create_runtime(
        kernel_db_path=tmp_path / "kernel.sqlite3",
        continuity_path=tmp_path / "continuity.sqlite3",
    )
    runtime.kernel.interrupts.request_global("stop before execution")
    first = await runtime.kernel.run(
        "Keep the baseline",
        "session-budget",
        budget=ResourceBudget(max_steps=4),
    )
    runtime.kernel.interrupts.clear_global()
    journal = runtime.kernel.continuity
    assert journal is not None
    baseline = journal.store.list_checkpoints()[-1]
    tracker = runtime.kernel._budgets[first.goal.id]
    tracker.snapshot.steps_used = 2
    runtime.kernel._persist_budget(first.goal.id, tracker)

    runtime.kernel.interrupts.request_global("stop the later goal")
    second = await runtime.kernel.run(
        "Spend a later budget",
        "session-budget",
        budget=ResourceBudget(max_steps=4),
    )
    runtime.kernel.interrupts.clear_global()
    assert runtime.kernel.store.get_budget(second.goal.id) is not None

    client = TestClient(create_app(runtime))
    missing = client.post(
        "/kernel/continuity/rollback",
        json={"checkpoint_id": "missing-checkpoint"},
    )
    assert missing.status_code == 409

    response = client.post(
        "/kernel/continuity/rollback",
        json={"checkpoint_id": baseline.checkpoint_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["modifies_worktree"] is False
    assert body["restores_approvals"] is False
    assert body["cryptographic_immutability"] is False
    assert body["checkpoint"]["reason"] == "rollback"
    assert body["checkpoint"]["parent_checkpoint_id"] == baseline.checkpoint_id
    assert runtime.kernel.goals.get(second.goal.id) is None
    assert runtime.kernel.store.get_budget(second.goal.id) is None
    surviving = runtime.kernel.store.get_budget(first.goal.id)
    assert surviving is not None
    assert surviving["steps_used"] == 2
    assert runtime.kernel.goals.require(first.goal.id).status is GoalStatus.INTERRUPTED


def test_rollback_restores_session_rows_into_memory(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    journal = runtime.kernel.continuity
    assert journal is not None
    original = Session(
        id="s-roll",
        user_id="ada",
        workspace_id="ws-a",
        metadata={"topic": "baseline"},
    )
    runtime.sessions.remember(runtime.persist_session(original))
    baseline = journal.publish(reason="sessions", kernel_id=runtime.kernel.state.kernel_id)
    replacement = original.model_copy(deep=True)
    replacement.workspace_id = "ws-b"
    replacement.metadata = {"topic": "later"}
    runtime.sessions.remember(runtime.persist_session(replacement))

    runtime.rollback_checkpoint(baseline.checkpoint_id)
    loaded = runtime.sessions.get("s-roll")
    assert loaded is not None
    assert loaded.workspace_id == "ws-a"
    assert loaded.metadata["topic"] == "baseline"
    assert journal.store.list_sessions()[0].workspace_id == "ws-a"
