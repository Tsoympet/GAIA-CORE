"""Model migration recorded when resume continues under a different model."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gaia.continuity.errors import ContinuityIntegrityError
from gaia.continuity.journal import ContinuityJournal
from gaia.continuity.records import ModelMigrationRequest
from gaia.continuity.store import ContinuityStore
from gaia.core.runtime import create_runtime
from gaia.kernel.goal_manager import GoalStatus
from gaia.security.policy import SecurityDecision, SecurityPolicy


class ApprovalRequiredPolicy(SecurityPolicy):
    """Admit work only after an in-process human approval."""

    def evaluate_objective(self, objective: str) -> SecurityDecision:
        decision = super().evaluate_objective(objective)
        if not decision.allowed:
            return decision
        return SecurityDecision(allowed=True, requires_human_approval=True)


@pytest.mark.asyncio
async def test_resume_migrates_a_model_change_without_granting_approval(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    journal = runtime.kernel.continuity
    assert journal is not None
    runtime.kernel.policy.security_policy = ApprovalRequiredPolicy()
    waiting = await runtime.kernel.run("Draft a local note", "session-migrate")
    assert waiting.goal.status is GoalStatus.WAITING_FOR_USER
    original = journal.model_id
    journal.model_id = "replacement-model"

    with pytest.raises(RuntimeError, match="no live in-process approval"):
        await runtime.kernel.resume(waiting.goal.id)

    migrations = journal.store.list_model_migrations()
    assert len(migrations) == 1
    assert migrations[0].from_model_id == original
    assert migrations[0].to_model_id == "replacement-model"
    assert migrations[0].automatic is True
    assert migrations[0].executes_task is False
    task = journal.store.get_task_by_goal(waiting.goal.id)
    assert task is not None
    assert journal.approval_is_live(task.task_id, task.action_fingerprint) is False

    runtime.kernel.grant_approval(waiting.goal.id, "operator")
    resumed = await runtime.kernel.resume(waiting.goal.id)
    assert resumed.goal.status is GoalStatus.COMPLETED
    assert len(journal.store.list_model_migrations()) == 1


@pytest.mark.asyncio
async def test_tool_policy_drift_blocks_resume_and_skips_migration(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    runtime.kernel.interrupts.request_global("stop before execution")
    interrupted = await runtime.kernel.run("Summarize the local runtime", "session-policy")
    assert interrupted.goal.status is GoalStatus.INTERRUPTED
    runtime.kernel.interrupts.clear_global()
    journal = runtime.kernel.continuity
    assert journal is not None
    journal.tool_policy = {"sandbox_required": False}
    with pytest.raises(RuntimeError, match="does not apply a different policy"):
        await runtime.kernel.resume(interrupted.goal.id)
    assert journal.store.list_model_migrations() == []


def test_schema_rollback_drops_model_migrations(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    journal = ContinuityJournal(ContinuityStore(path), model_id="first")
    journal.publish(reason="baseline", kernel_id="kernel-1")
    journal.model_id = "second"
    migrated = journal.migrate_model_for_resume(kernel_id="kernel-1")
    assert migrated is not None
    assert migrated.executes_task is False
    store = ContinuityStore(path)
    assert store.rollback_schema(3, force=True) == 3
    with sqlite3.connect(path) as connection:
        names = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert "model_migrations" not in names
    assert "process_snapshots" in names
    reopened = ContinuityStore(path)
    assert reopened.schema_version() == 4
    assert reopened.list_model_migrations() == []


def test_migration_cannot_claim_that_it_executes_the_task(tmp_path: Path) -> None:
    store = ContinuityStore(tmp_path / "continuity.sqlite3")
    request = ModelMigrationRequest(
        from_checkpoint_id="missing",
        from_model_id="a",
        to_model_id="b",
        from_model_configuration_sha256="1",
        to_model_configuration_sha256="2",
        reason="resume continued under the current model",
        executes_task=True,
        automatic=True,
    )
    with pytest.raises(ContinuityIntegrityError, match="does not execute a task"):
        store.publish_checkpoint(
            reason="bad",
            kernel_id="kernel-1",
            model_migration=request,
        )
