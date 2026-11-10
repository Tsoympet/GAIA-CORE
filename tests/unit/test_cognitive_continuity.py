"""Tests for durable cognitive continuity, recovery, and approval revocation."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from gaia.continuity.errors import ContinuityIntegrityError, ContinuityLockedError
from gaia.continuity.journal import ContinuityJournal
from gaia.continuity.store import ContinuityStore
from gaia.continuity.task_state import TaskState, TaskTransitionError, validate_transition
from gaia.core.runtime import create_runtime
from gaia.kernel.context_manager import ContextManager
from gaia.kernel.goal_manager import Goal, GoalStatus
from gaia.kernel.resource_budget import ResourceBudget
from gaia.security.policy import SecurityDecision, SecurityPolicy


class ApprovalRequiredPolicy(SecurityPolicy):
    """Admit work only after an in-process human approval."""

    def evaluate_objective(self, objective: str) -> SecurityDecision:
        decision = super().evaluate_objective(objective)
        if not decision.allowed:
            return decision
        return SecurityDecision(allowed=True, requires_human_approval=True)


def test_task_transitions_reject_illegal_edges() -> None:
    validate_transition(TaskState.CREATED, TaskState.CLASSIFIED)
    with pytest.raises(TaskTransitionError):
        validate_transition(TaskState.CREATED, TaskState.COMPLETED)
    with pytest.raises(TaskTransitionError):
        validate_transition(TaskState.COMPLETED, TaskState.EXECUTING)


def test_store_redacts_and_reloads_goal_and_context(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    goal = Goal(
        objective="Inspect a local drawing",
        session_id="session-1",
        capabilities=["reasoning"],
        metadata={"approval_token": "do-not-persist", "topic": "hull"},
    )
    stored_goal = store.upsert_goal(goal)
    assert stored_goal.metadata["approval_token"] == "[redacted]"
    assert stored_goal.metadata["topic"] == "hull"
    assert goal.metadata["approval_token"] == "do-not-persist"

    contexts = ContextManager()
    contexts.bind(goal.id, goal.session_id)
    contexts.put(goal.id, "approval_token", "secret-token")
    contexts.put(goal.id, "note", {"api_key": "abc", "keep": 1})
    context = contexts.get(goal.id)
    assert context is not None
    store.upsert_context(context)
    store.transition_task(goal, TaskState.CREATED, "goal created")

    reloaded = ContinuityStore(path)
    loaded_goal = reloaded.get_goal(goal.id)
    assert loaded_goal is not None
    assert loaded_goal.metadata["approval_token"] == "[redacted]"
    assert loaded_goal.metadata["topic"] == "hull"
    loaded_context = reloaded.list_contexts()[0]
    values = {item.key: item.value for item in loaded_context.items}
    assert values["approval_token"] == "[redacted]"
    assert values["note"] == {"api_key": "[redacted]", "keep": 1}
    assert reloaded.get_task_by_goal(goal.id) is not None


def test_recovery_interrupts_inflight_work_and_revokes_approvals(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    goal = Goal(objective="Run a local check", session_id="session-2")
    store.upsert_goal(goal)
    store.transition_task(goal, TaskState.CREATED, "goal created")
    store.transition_task(goal, TaskState.CLASSIFIED, "classified")
    task = store.transition_task(goal, TaskState.EXECUTING, "started")
    store.record_approval_event(
        task_id=task.task_id,
        goal_id=goal.id,
        action_fingerprint=task.action_fingerprint,
        approver="operator",
        decision="approve",
        process_nonce="process-a",
    )
    goal.status = GoalStatus.ACTIVE
    store.upsert_goal(goal)

    report = ContinuityStore(path).recover()

    recovered = ContinuityStore(path)
    loaded = recovered.get_goal(goal.id)
    assert loaded is not None
    assert loaded.status is GoalStatus.INTERRUPTED
    assert goal.id in report.interrupted_goal_ids
    loaded_task = recovered.get_task_by_goal(goal.id)
    assert loaded_task is not None
    assert loaded_task.state is TaskState.INTERRUPTED
    approvals = recovered.list_approval_events()
    assert approvals[0].expired is True
    assert approvals[0].reusable is False
    assert approvals[0].approval_id in report.revoked_approval_ids
    assert recovered.verify_chain() is True


def test_abandoned_draft_is_quarantined_and_not_authoritative(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    store.migrate()
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO checkpoints (
                checkpoint_id, parent_checkpoint_id, schema_version, reason,
                payload_json, payload_sha256, previous_hash, publication,
                created_at, kernel_id
            ) VALUES ('draft-1', NULL, 1, 'crash', '{"approval_token":"sekret"}',
                      'deadbeef', 'genesis', 'draft', '2026-01-01T00:00:00+00:00', 'test')
            """
        )
    report = ContinuityStore(path).recover()
    reloaded = ContinuityStore(path)
    assert "draft-1" in report.quarantined_ids
    published = reloaded.list_checkpoints()
    assert all(item.checkpoint_id != "draft-1" for item in published)
    assert any(item.reason == "post_recovery" for item in published)
    quarantine = reloaded.list_quarantine()
    assert quarantine[0].kind == "abandoned_draft"
    assert "sekret" not in quarantine[0].payload_json


def test_tampered_checkpoint_fails_verification(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    checkpoint = store.publish_checkpoint(reason="baseline", kernel_id="test")
    assert store.verify_checkpoint(checkpoint.checkpoint_id) is True
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
            ('{"goals":[],"tampered":true}', checkpoint.checkpoint_id),
        )
    assert ContinuityStore(path).verify_checkpoint(checkpoint.checkpoint_id) is False
    report = ContinuityStore(path).recover()
    assert checkpoint.checkpoint_id in report.quarantined_ids
    assert report.integrity_ok is False
    published = ContinuityStore(path).list_checkpoints()
    assert checkpoint.checkpoint_id not in {item.checkpoint_id for item in published}
    assert any(item.reason == "post_recovery" for item in published)
    assert ContinuityStore(path).verify_chain() is True


def test_schema_rollback_requires_force_and_can_be_reapplied(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    store.publish_checkpoint(reason="keep", kernel_id="test")
    with pytest.raises(ContinuityIntegrityError):
        store.rollback_schema(0)
    assert store.rollback_schema(0, force=True) == 0
    with sqlite3.connect(path) as connection:
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "goals" not in names
    assert "checkpoints" not in names
    assert ContinuityStore(path).schema_version() == 3


def test_branch_redacts_policy_secrets_and_requires_verified_parent(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    checkpoint = store.publish_checkpoint(reason="fork-point", kernel_id="test")
    branch = store.create_branch(
        checkpoint.checkpoint_id,
        "explore a local alternative",
        {"provider": "ollama", "api_key": "hidden"},
        {"sandbox_required": True, "approval_token": "hidden"},
    )
    assert branch.model_configuration["api_key"] == "[redacted]"
    assert branch.tool_policy["approval_token"] == "[redacted]"
    assert branch.tool_policy["sandbox_required"] is True
    assert branch.memory_snapshot_hash == checkpoint.payload_sha256
    with pytest.raises(ContinuityIntegrityError):
        store.create_branch("missing", "nope", {}, {})


def test_rollback_restores_snapshot_without_resuming_execution(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    goal = Goal(objective="Keep the baseline", session_id="session-3", status=GoalStatus.COMPLETED)
    store.upsert_goal(goal)
    store.transition_task(goal, TaskState.CREATED, "goal created")
    store.transition_task(goal, TaskState.CLASSIFIED, "classified")
    store.transition_task(goal, TaskState.EXECUTING, "started")
    store.transition_task(goal, TaskState.VERIFYING, "verify")
    store.transition_task(goal, TaskState.COMPLETED, "done")
    baseline = store.publish_checkpoint(reason="baseline", kernel_id="test")

    later = Goal(objective="Later work", session_id="session-3")
    store.upsert_goal(later)
    store.transition_task(later, TaskState.CREATED, "goal created")
    store.publish_checkpoint(reason="later", kernel_id="test")

    restored = store.rollback_to(baseline.checkpoint_id)
    assert restored.reason == "rollback"
    assert restored.parent_checkpoint_id == baseline.checkpoint_id
    assert store.verify_chain() is True
    assert store.get_goal(later.id) is None
    assert store.get_goal(goal.id) is not None
    assert store.get_task_by_goal(goal.id) is not None
    assert store.get_task_by_goal(goal.id).state is TaskState.COMPLETED


def test_live_lock_blocks_recovery_and_dead_lock_can_be_replaced(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    store.migrate()
    process = subprocess.Popen(["sleep", "30"])
    store.lock_path.write_text(str(process.pid), encoding="utf-8")
    try:
        with pytest.raises(ContinuityLockedError):
            store.recover()
    finally:
        process.kill()
        process.wait(timeout=5)

    store.lock_path.write_text(str(process.pid), encoding="utf-8")
    report = store.recover()
    assert report.schema_version == 3
    assert store.lock_path.read_text(encoding="utf-8").strip() == str(__import__("os").getpid())


def test_injected_secret_is_removed_on_recovery(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    goal = Goal(objective="Local note", session_id="session-4", metadata={"topic": "kept"})
    store.upsert_goal(goal)
    loaded = store.get_goal(goal.id)
    assert loaded is not None
    payload = loaded.model_dump(mode="json")
    payload["metadata"] = {"topic": "kept", "approval_token": "restored-secret"}
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE goals SET goal_json = ? WHERE goal_id = ?",
            (__import__("json").dumps(payload), goal.id),
        )
    ContinuityStore(path).recover()
    redacted = ContinuityStore(path).get_goal(goal.id)
    assert redacted is not None
    assert redacted.metadata["approval_token"] == "[redacted]"
    assert redacted.metadata["topic"] == "kept"


@pytest.mark.asyncio
async def test_kernel_run_persists_across_runtime_restart(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    runtime = create_runtime(continuity_path=path)
    result = await runtime.kernel.run(
        "Analyze the GAIA bootstrap runtime",
        "session-kernel",
        ["reasoning"],
        metadata={"approval_token": "sekret", "topic": "kernel"},
    )
    assert result.goal.status is GoalStatus.COMPLETED
    assert result.goal.metadata["approval_token"] == "[redacted]"
    assert result.goal.metadata["topic"] == "kernel"
    journal = runtime.kernel.continuity
    assert journal is not None
    assert journal.store.verify_chain() is True
    assert journal.store.list_checkpoints()

    restarted = create_runtime(continuity_path=path)
    restored = restarted.kernel.goals.get(result.goal.id)
    assert restored is not None
    assert restored.status is GoalStatus.COMPLETED
    assert restored.metadata["approval_token"] == "[redacted]"
    assert restarted.kernel.contexts.get(result.goal.id) is not None
    restarted_journal = restarted.kernel.continuity
    assert restarted_journal is not None
    assert restarted_journal.store.get_task_by_goal(result.goal.id) is not None
    assert (
        restarted_journal.store.get_task_by_goal(result.goal.id).state is TaskState.COMPLETED
    )


@pytest.mark.asyncio
async def test_resume_reexecutes_interrupted_goal_without_restoring_approvals(
    tmp_path: Path,
) -> None:
    path = tmp_path / "continuity.sqlite3"
    runtime = create_runtime(continuity_path=path)
    runtime.kernel.interrupts.request_global("stop before execution")
    interrupted = await runtime.kernel.run("Summarize the local runtime", "session-resume")
    assert interrupted.goal.status is GoalStatus.INTERRUPTED
    runtime.kernel.interrupts.clear_global()

    resumed = await runtime.kernel.resume(interrupted.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED
    assert resumed.verification is not None
    assert resumed.verification.passed is True
    task = runtime.kernel.continuity
    assert task is not None
    assert task.store.get_task_by_goal(interrupted.goal.id) is not None
    assert task.store.get_task_by_goal(interrupted.goal.id).state is TaskState.COMPLETED


@pytest.mark.asyncio
async def test_waiting_approval_is_process_local_and_not_restored(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    runtime = create_runtime(continuity_path=path)
    assert runtime.kernel.continuity is not None
    runtime.kernel.policy.security_policy = ApprovalRequiredPolicy()

    waiting = await runtime.kernel.run("Draft a local note", "session-approval")
    assert waiting.response.status == "waiting_for_user"
    assert waiting.goal.status is GoalStatus.WAITING_FOR_USER
    with pytest.raises(RuntimeError, match="no live in-process approval"):
        await runtime.kernel.resume(waiting.goal.id)

    runtime.kernel.grant_approval(waiting.goal.id, "operator")
    fresh = ContinuityJournal(runtime.kernel.continuity.store)
    task = runtime.kernel.continuity.store.get_task_by_goal(waiting.goal.id)
    assert task is not None
    assert fresh.approval_is_live(task.task_id, task.action_fingerprint) is False
    assert runtime.kernel.continuity.approval_is_live(task.task_id, task.action_fingerprint)

    resumed = await runtime.kernel.resume(waiting.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED

    recovered = ContinuityStore(path).recover()
    assert recovered.revoked_approval_ids
    reloaded = ContinuityStore(path).get_task_by_goal(waiting.goal.id)
    assert reloaded is not None
    assert reloaded.state is TaskState.COMPLETED


@pytest.mark.asyncio
async def test_budget_failure_is_persisted(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    runtime = create_runtime(continuity_path=path)
    result = await runtime.kernel.run(
        "Tiny budget task",
        "session-budget",
        budget=ResourceBudget(max_steps=0),
    )
    assert result.goal.status is GoalStatus.FAILED
    journal = runtime.kernel.continuity
    assert journal is not None
    task = journal.store.get_task_by_goal(result.goal.id)
    assert task is not None
    assert task.state is TaskState.FAILED
    assert task.budget["exhausted_resource"] == "steps"


def test_delete_goal_removes_live_rows_and_keeps_checkpoint(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    goal = Goal(objective="Temporary note", session_id="session-5")
    store.upsert_goal(goal)
    store.transition_task(goal, TaskState.CREATED, "goal created")
    checkpoint = store.publish_checkpoint(reason="before-delete", kernel_id="test")
    assert store.delete_goal(goal.id, "operator requested deletion") is True
    assert store.get_goal(goal.id) is None
    assert store.get_task_by_goal(goal.id) is None
    retained = store.get_checkpoint(checkpoint.checkpoint_id)
    assert retained is not None
    assert store.verify_checkpoint(checkpoint.checkpoint_id) is True
    assert "Temporary note" in (retained.payload_json or "")
    tombstones = [item for item in store.list_quarantine() if item.kind == "deletion_tombstone"]
    assert tombstones
    assert "Temporary note" not in tombstones[0].payload_json
    bundle = store.export_audit_bundle()
    assert bundle["cryptographic_immutability"] is False
    assert bundle["network"] == "none"
    assert bundle["integrity_ok"] is True


def test_cli_continuity_inspects_without_requiring_a_runtime(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from gaia.cli import app

    runner = CliRunner()
    missing = runner.invoke(app, ["continuity", "--db", str(tmp_path / "missing.sqlite3")])
    assert missing.exit_code == 0
    assert "unavailable" in missing.stdout

    journal = tmp_path / "journal.sqlite3"
    ContinuityStore(journal).publish_checkpoint(reason="cli", kernel_id="test")
    present = runner.invoke(app, ["continuity", "--db", str(journal)])
    assert present.exit_code == 0
    assert "available" in present.stdout
    assert "False" in present.stdout


def test_other_process_lock_message_names_the_holder(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    store.migrate()
    process = subprocess.Popen(["sleep", "30"])
    store.lock_path.write_text(str(process.pid), encoding="utf-8")
    try:
        with pytest.raises(ContinuityLockedError) as exc:
            store.recover()
        assert exc.value.holder == str(process.pid)
    finally:
        process.kill()
        process.wait(timeout=5)
