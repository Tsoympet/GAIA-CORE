"""Process-local continuity journal over the durable store."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.continuity.codec import json_object
from gaia.continuity.errors import ContinuityIntegrityError
from gaia.continuity.records import ApprovalEvent, Checkpoint, RecoveryReport, TaskRun
from gaia.continuity.redaction import is_sensitive_key, redact_mapping, redact_value
from gaia.continuity.snapshots import (
    EnvironmentComparison,
    ProcessObservation,
    compare_environment,
    observe_process,
    observe_repository,
)
from gaia.continuity.store import ContinuityStore
from gaia.continuity.task_state import TaskState
from gaia.kernel.context_manager import ContextManager, WorkingContext
from gaia.kernel.goal_manager import Goal, GoalManager

if TYPE_CHECKING:
    from gaia.core.event_bus import EventBus
    from gaia.core.session import Session

LIMITATIONS: tuple[str, ...] = (
    "The SQLite hash chain detects corruption and naive tampering. It is not "
    "cryptographic immutability against a privileged local writer.",
    "Approval decisions are process-local, non-reusable, and revoked on recovery. "
    "Approval tokens and credentials are not restored.",
    "Published checkpoints are retained after live goal deletion.",
    "When the orchestrator plans internally, the task machine records "
    "classified to executing rather than a separate planned state.",
    "Field encryption is off unless a 32-byte data key is configured. "
    "Encryption does not make the hash chain cryptographic immutability.",
    "A second live process cannot recover or mutate a locked journal.",
    "Session records restore the id, user id, workspace id, creation time, and "
    "redacted metadata. They do not restore approval grants.",
    "Continuity events are a live process stream over the EventBus. They are not "
    "a second durable ledger and they are not cryptographic immutability.",
    "Repository and process snapshots are observations. Rollback and resume do "
    "not change the git worktree, revive the publishing process, or switch models.",
)


class ContinuityEvent(BaseModel):
    """One live continuity event. Payloads omit checkpoint bodies and secrets."""

    event_id: str
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ContinuityJournal:
    """Kernel-facing continuity API.

    Live approval grants stay in this process. The database stores only an
    expired-on-recovery audit event and never a reusable credential.
    """

    def __init__(
        self,
        store: ContinuityStore,
        recovery: RecoveryReport | None = None,
        *,
        event_bus: EventBus | None = None,
        repository_root: Path | None = None,
        model_id: str = "",
        model_configuration: dict[str, Any] | None = None,
        tool_policy: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.recovery = recovery
        self.event_bus = event_bus
        self.repository_root = repository_root
        self.model_id = model_id
        self.model_configuration = dict(model_configuration or {})
        self.tool_policy = dict(tool_policy or {})
        self.process_nonce = str(uuid4())
        self._grants: dict[str, str] = {}
        self._recent: deque[ContinuityEvent] = deque(maxlen=256)
        if recovery is not None:
            self._emit(
                "recovery",
                {
                    "integrity_ok": recovery.integrity_ok,
                    "interrupted_goals": list(recovery.interrupted_goal_ids),
                    "revoked_approvals": len(recovery.revoked_approval_ids),
                    "quarantined": len(recovery.quarantined_ids),
                    "cryptographic_immutability": False,
                },
            )

    def capability_status(self) -> str:
        """Return available, degraded, or unavailable."""
        if self.recovery is not None and not self.recovery.integrity_ok:
            return "degraded"
        return "available"

    def status_summary(self) -> dict[str, Any]:
        """Return operator status for the configured journal."""
        summary = self.store.status_summary(self.recovery)
        if summary.get("status") != "unavailable":
            summary["status"] = self.capability_status()
        summary["limitations"] = list(LIMITATIONS)
        summary["approvals_reusable"] = False
        summary["streaming"] = self.event_bus is not None
        summary["recent_event_count"] = len(self._recent)
        summary["model_id"] = self.model_id
        summary["repository_root"] = (
            None if self.repository_root is None else str(self.repository_root)
        )
        summary["modifies_worktree"] = False
        summary["resumes_process"] = False
        summary["switches_model"] = False
        return summary

    def recent_events(self) -> list[ContinuityEvent]:
        """Return the process-local continuity event window."""
        return list(self._recent)

    def hydrate(
        self,
        goals: GoalManager,
        contexts: ContextManager,
        *,
        replace: bool = False,
    ) -> None:
        """Load recovered goals and working context into the kernel."""
        loaded_goals = self.store.list_goals()
        loaded_contexts = self.store.list_contexts()
        if replace:
            goals.replace_all(loaded_goals)
            contexts.replace_all(loaded_contexts)
            return
        for goal in loaded_goals:
            goals.restore(goal)
        for context in loaded_contexts:
            contexts.restore(context)

    def remember_session(self, session: Session) -> Session:
        """Persist a session and redact secret metadata in the live object."""
        session.metadata = redact_mapping(session.metadata)
        return self.store.upsert_session(session)

    def record(self, goal: Goal, state: TaskState, reason: str) -> TaskRun:
        """Persist a goal and advance its task state."""
        goal.metadata = redact_mapping(goal.metadata)
        self.store.ensure_session(goal.session_id)
        self.store.upsert_goal(goal)
        task = self.store.transition_task(goal, state, reason)
        self._emit(
            "task_transitioned",
            {
                "task_id": task.task_id,
                "goal_id": goal.id,
                "state": task.state.value,
                "reason": reason,
            },
        )
        return task

    def record_context(self, context: WorkingContext) -> None:
        """Persist working context after redacting sensitive values."""
        for item in context.items:
            if is_sensitive_key(item.key):
                item.value = "[redacted]"
            else:
                item.value = redact_value(item.value)
        self.store.upsert_context(context)

    def publish(
        self,
        *,
        reason: str,
        kernel_id: str,
        parent_checkpoint_id: str | None = None,
    ) -> Checkpoint:
        """Publish a verified checkpoint of the current journal."""
        repository = observe_repository(self.repository_root)
        process = self._observe_process(kernel_id)
        checkpoint = self.store.publish_checkpoint(
            reason=reason,
            kernel_id=kernel_id,
            parent_checkpoint_id=parent_checkpoint_id,
            repository=repository,
            process=process,
        )
        self._emit(
            "checkpoint_published",
            {
                "checkpoint_id": checkpoint.checkpoint_id,
                "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
                "reason": checkpoint.reason,
                "publication": checkpoint.publication,
                "payload_sha256": checkpoint.payload_sha256,
                "cryptographic_immutability": False,
                "repository_available": repository.available,
                "repository_dirty": repository.dirty,
                "head_commit": repository.head_commit,
                "model_id": process.model_id,
                "modifies_worktree": False,
                "resumes_process": False,
                "switches_model": False,
            },
        )
        return checkpoint

    def environment_report(self, checkpoint_id: str | None = None) -> dict[str, Any]:
        """Compare a stored environment observation with this process."""
        checkpoint = self._environment_checkpoint(checkpoint_id)
        if checkpoint is None:
            return {
                "checkpoint_id": None,
                "repository": None,
                "process": None,
                "comparison": EnvironmentComparison(comparable=False).model_dump(mode="json"),
                "cryptographic_immutability": False,
                "modifies_worktree": False,
                "resumes_process": False,
                "switches_model": False,
            }
        comparison = self._compare(checkpoint)
        repository = self.store.get_repository_snapshot(checkpoint.checkpoint_id)
        process = self.store.get_process_snapshot(checkpoint.checkpoint_id)
        return {
            "checkpoint_id": checkpoint.checkpoint_id,
            "repository": None if repository is None else repository.model_dump(mode="json"),
            "process": None if process is None else process.model_dump(mode="json"),
            "comparison": comparison.model_dump(mode="json"),
            "cryptographic_immutability": False,
            "modifies_worktree": False,
            "resumes_process": False,
            "switches_model": False,
        }

    def assert_resume_current(self) -> None:
        """Refuse resume when the worktree, model, or tool policy no longer matches.

        A missing environment observation does not block resume. Resume never
        checks out commits, restarts the publishing process, or switches models.
        """
        checkpoint = self._environment_checkpoint(None)
        if checkpoint is None:
            return
        comparison = self._compare(checkpoint)
        if not comparison.blocks_resume():
            return
        reason = (
            comparison.notes[0]
            if comparison.notes
            else "environment observation blocks resume"
        )
        raise ContinuityIntegrityError(reason)

    def rollback(self, checkpoint_id: str, *, kernel_id: str) -> Checkpoint:
        """Restore live state from a verified checkpoint and emit a live event."""
        checkpoint = self.store.rollback_to(checkpoint_id, kernel_id=kernel_id)
        self._emit(
            "rolled_back",
            {
                "checkpoint_id": checkpoint.checkpoint_id,
                "reason": checkpoint.reason,
                "cryptographic_immutability": False,
            },
        )
        return checkpoint

    def approval_is_live(self, task_id: str, fingerprint: str) -> bool:
        """Return whether this process granted approval for the exact action."""
        return self._grants.get(task_id) == fingerprint

    def grant(self, goal: Goal, approver: str) -> ApprovalEvent:
        """Record a non-reusable approval and keep the grant in memory only."""
        task = self._require_task(goal.id)
        if task.state is not TaskState.WAITING_FOR_USER:
            raise RuntimeError(
                "approval can only be granted while the task is waiting_for_user"
            )
        event = self.store.record_approval_event(
            task_id=task.task_id,
            goal_id=goal.id,
            action_fingerprint=task.action_fingerprint,
            approver=approver,
            decision="approve",
            process_nonce=self.process_nonce,
        )
        self._grants[task.task_id] = task.action_fingerprint
        self._emit(
            "approval_recorded",
            {
                "goal_id": goal.id,
                "task_id": task.task_id,
                "decision": "approve",
                "approver": approver,
                "reusable": False,
            },
        )
        return event

    def deny(self, goal: Goal, approver: str) -> ApprovalEvent:
        """Record a denial and drop any in-process grant for the task."""
        task = self._require_task(goal.id)
        event = self.store.record_approval_event(
            task_id=task.task_id,
            goal_id=goal.id,
            action_fingerprint=task.action_fingerprint,
            approver=approver,
            decision="deny",
            process_nonce=self.process_nonce,
        )
        self._grants.pop(task.task_id, None)
        self._emit(
            "approval_recorded",
            {
                "goal_id": goal.id,
                "task_id": task.task_id,
                "decision": "deny",
                "approver": approver,
                "reusable": False,
            },
        )
        return event

    def _emit(self, name: str, payload: dict[str, Any]) -> ContinuityEvent:
        """Record a live event. Checkpoint bodies and secrets are not included."""
        event = ContinuityEvent(
            event_id=str(uuid4()),
            name=name,
            payload=dict(payload),
            created_at=datetime.now(UTC),
        )
        self._recent.append(event)
        if self.event_bus is None:
            return event
        from gaia.core.event_bus import Event, EventDomain

        bus_event = Event(
            domain=EventDomain.CONTINUITY,
            name=name,
            payload={"event_id": event.event_id, **event.payload},
            trace_id=str(event.payload.get("goal_id") or event.payload.get("checkpoint_id") or ""),
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return event
        loop.create_task(self.event_bus.publish(bus_event))
        return event

    def _observe_process(self, kernel_id: str) -> ProcessObservation:
        return observe_process(
            kernel_id=kernel_id,
            process_nonce=self.process_nonce,
            model_id=self.model_id,
            model_configuration=self.model_configuration,
            tool_policy=self.tool_policy,
        )

    def _environment_checkpoint(self, checkpoint_id: str | None) -> Checkpoint | None:
        if checkpoint_id is None:
            return self.store.latest_environment_checkpoint()
        checkpoint = self.store.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise KeyError(f"unknown checkpoint: {checkpoint_id}")
        return checkpoint

    def _compare(self, checkpoint: Checkpoint) -> EnvironmentComparison:
        if checkpoint.payload_json is None:
            raise ContinuityIntegrityError("checkpoint payload is missing")
        payload = json_object(checkpoint.payload_json)
        repository_payload = payload.get("repository")
        process_payload = payload.get("process")
        repository_section = repository_payload if isinstance(repository_payload, dict) else None
        process_section = process_payload if isinstance(process_payload, dict) else None
        return compare_environment(
            repository_payload=repository_section,
            process_payload=process_section,
            repository_row=self.store.get_repository_snapshot(checkpoint.checkpoint_id),
            process_row=self.store.get_process_snapshot(checkpoint.checkpoint_id),
            live_repository=observe_repository(self.repository_root),
            live_process=self._observe_process(checkpoint.kernel_id),
        )

    def _require_task(self, goal_id: str) -> TaskRun:
        task = self.store.get_task_by_goal(goal_id)
        if task is None:
            raise KeyError(f"unknown continuity task for goal: {goal_id}")
        return task
