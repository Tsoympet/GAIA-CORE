"""Resume rechecks named permissions and exhausted budgets before it reruns."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gaia.continuity.task_state import TaskState
from gaia.core.runtime import create_runtime
from gaia.kernel.goal_manager import GoalStatus
from gaia.kernel.resource_budget import BudgetSnapshot, ResourceBudget
from gaia.kernel.resume_gate import exhausted_resume_resource, named_permissions
from gaia.security.permission_manager import Permission
from gaia.server.app import create_app


def test_named_permissions_ignore_routing_labels() -> None:
    assert named_permissions(["coding", "file.read", "file.read", "repo"]) == [
        Permission.FILE_READ
    ]


def test_step_budget_at_its_limit_blocks_resume() -> None:
    snapshot = BudgetSnapshot(budget=ResourceBudget(max_steps=1), steps_used=1)
    assert exhausted_resume_resource(snapshot) == "steps"
    snapshot.steps_used = 0
    assert exhausted_resume_resource(snapshot) is None


@pytest.mark.asyncio
async def test_resume_refuses_a_revoked_permission_without_granting_it(
    tmp_path: Path,
) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    manager = runtime.kernel.policy.permission_manager
    manager.grant(Permission.FILE_READ, "*", "operator grant")
    runtime.kernel.interrupts.request_global("stop before execution")
    waiting = await runtime.kernel.run(
        "Read a local note",
        "session-permission",
        ["file.read", "coding"],
    )
    assert waiting.goal.status is GoalStatus.INTERRUPTED
    runtime.kernel.interrupts.clear_global()
    manager.deny(Permission.FILE_READ, "*", "revoked before resume")
    rules_before = len(manager.rules)
    journal = runtime.kernel.continuity
    assert journal is not None
    journal.model_id = "replacement-model"

    with pytest.raises(RuntimeError, match="does not apply a stale permission: file.read"):
        await runtime.kernel.resume(waiting.goal.id)

    assert runtime.kernel.goals.require(waiting.goal.id).status is GoalStatus.INTERRUPTED
    task = journal.store.get_task_by_goal(waiting.goal.id)
    assert task is not None
    assert task.state is TaskState.INTERRUPTED
    assert journal.store.list_model_migrations() == []
    assert len(manager.rules) == rules_before
    assert manager.rules[-1].allowed is False

    manager.grant(Permission.FILE_READ, "*", "restored grant")
    resumed = await runtime.kernel.resume(waiting.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED
    assert len(journal.store.list_model_migrations()) == 1


@pytest.mark.asyncio
async def test_resume_does_not_treat_a_risky_grant_as_human_approval(
    tmp_path: Path,
) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    manager = runtime.kernel.policy.permission_manager
    manager.grant(Permission.SHELL_COMMAND, "*", "unapproved grant", human_approved=False)
    runtime.kernel.interrupts.request_global("stop before execution")
    interrupted = await runtime.kernel.run(
        "Inspect the shell policy",
        "session-shell",
        ["shell.command"],
    )
    runtime.kernel.interrupts.clear_global()

    with pytest.raises(RuntimeError, match="does not apply a stale permission: shell.command"):
        await runtime.kernel.resume(interrupted.goal.id)

    assert runtime.kernel.goals.require(interrupted.goal.id).status is GoalStatus.INTERRUPTED
    manager.grant(Permission.SHELL_COMMAND, "*", "human grant", human_approved=True)
    resumed = await runtime.kernel.resume(interrupted.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED


@pytest.mark.asyncio
async def test_resume_refuses_an_exhausted_budget_without_resetting_it(
    tmp_path: Path,
) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    runtime.kernel.interrupts.request_global("stop before execution")
    interrupted = await runtime.kernel.run(
        "Stay inside the budget",
        "session-budget",
        ["coding"],
        budget=ResourceBudget(max_steps=4),
    )
    runtime.kernel.interrupts.clear_global()
    tracker = runtime.kernel._budgets[interrupted.goal.id]
    tracker.snapshot.steps_used = tracker.budget.max_steps
    tracker.snapshot.exhausted_resource = None
    runtime.kernel._persist_budget(interrupted.goal.id, tracker)

    with pytest.raises(RuntimeError, match="exhausted resource budget: steps"):
        await runtime.kernel.resume(interrupted.goal.id)

    assert tracker.snapshot.steps_used == 4
    assert runtime.kernel.goals.require(interrupted.goal.id).status is GoalStatus.INTERRUPTED
    stored = runtime.kernel.store.get_budget(interrupted.goal.id)
    assert stored is not None
    assert stored["steps_used"] == 4

    tracker.snapshot.steps_used = 1
    runtime.kernel._persist_budget(interrupted.goal.id, tracker)
    resumed = await runtime.kernel.resume(interrupted.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED


@pytest.mark.asyncio
async def test_kill_switch_blocks_resume_of_a_risky_permission(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    manager = runtime.kernel.policy.permission_manager
    manager.grant(Permission.SHELL_COMMAND, "*", "human grant", human_approved=True)
    runtime.kernel.interrupts.request_global("stop before execution")
    interrupted = await runtime.kernel.run(
        "Inspect the shell policy",
        "session-kill",
        ["shell.command"],
    )
    runtime.kernel.interrupts.clear_global()
    manager.activate_kill_switch("stop resume")

    with pytest.raises(RuntimeError, match="does not apply a stale permission: shell.command"):
        await runtime.kernel.resume(interrupted.goal.id)

    assert manager.kill_switch.enabled is True
    assert runtime.kernel.goals.require(interrupted.goal.id).status is GoalStatus.INTERRUPTED
    manager.deactivate_kill_switch()
    resumed = await runtime.kernel.resume(interrupted.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED


@pytest.mark.asyncio
async def test_resume_route_reports_a_stale_permission(tmp_path: Path) -> None:
    runtime = create_runtime(
        kernel_db_path=tmp_path / "kernel.sqlite3",
        continuity_path=tmp_path / "continuity.sqlite3",
    )
    runtime.kernel.interrupts.request_global("stop before execution")
    interrupted = await runtime.kernel.run(
        "Inspect the shell policy",
        "session-api",
        ["shell.command"],
    )
    runtime.kernel.interrupts.clear_global()
    client = TestClient(create_app(runtime))
    response = client.post(f"/kernel/goals/{interrupted.goal.id}/resume", json={})
    assert response.status_code == 409
    assert "stale permission: shell.command" in response.json()["detail"]
    assert runtime.kernel.goals.require(interrupted.goal.id).status is GoalStatus.INTERRUPTED
