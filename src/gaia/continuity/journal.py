"""Process-local continuity journal over the durable store."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.continuity.records import ApprovalEvent, Checkpoint, RecoveryReport, TaskRun
from gaia.continuity.redaction import is_sensitive_key, redact_mapping, redact_value
from gaia.continuity.store import ContinuityStore
from gaia.continuity.task_state import TaskState
from gaia.core.event_bus import Event, EventBus, EventDomain
from gaia.core.session import Session
from gaia.kernel.context_manager import ContextManager, WorkingContext
from gaia.kernel.goal_manager import Goal, GoalManager

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
    ) -> None:
        self.store = store
        self.recovery = recovery
        self.event_bus = event_bus
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
        checkpoint = self.store.publish_checkpoint(
            reason=reason,
            kernel_id=kernel_id,
            parent_checkpoint_id=parent_checkpoint_id,
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
            },
        )
        return checkpoint

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

    def _require_task(self, goal_id: str) -> TaskRun:
        task = self.store.get_task_by_goal(goal_id)
        if task is None:
            raise KeyError(f"unknown continuity task for goal: {goal_id}")
        return task
