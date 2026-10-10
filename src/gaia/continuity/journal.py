"""Process-local continuity journal over the durable store."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from gaia.continuity.records import ApprovalEvent, Checkpoint, RecoveryReport, TaskRun
from gaia.continuity.redaction import is_sensitive_key, redact_mapping, redact_value
from gaia.continuity.store import ContinuityStore
from gaia.continuity.task_state import TaskState
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
)


class ContinuityJournal:
    """Kernel-facing continuity API.

    Live approval grants stay in this process. The database stores only an
    expired-on-recovery audit event and never a reusable credential.
    """

    def __init__(
        self,
        store: ContinuityStore,
        recovery: RecoveryReport | None = None,
    ) -> None:
        self.store = store
        self.recovery = recovery
        self.process_nonce = str(uuid4())
        self._grants: dict[str, str] = {}

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
        return summary

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

    def record(self, goal: Goal, state: TaskState, reason: str) -> TaskRun:
        """Persist a goal and advance its task state."""
        goal.metadata = redact_mapping(goal.metadata)
        self.store.ensure_session(goal.session_id)
        self.store.upsert_goal(goal)
        return self.store.transition_task(goal, state, reason)

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
        return self.store.publish_checkpoint(
            reason=reason,
            kernel_id=kernel_id,
            parent_checkpoint_id=parent_checkpoint_id,
        )

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
        return event

    def _require_task(self, goal_id: str) -> TaskRun:
        task = self.store.get_task_by_goal(goal_id)
        if task is None:
            raise KeyError(f"unknown continuity task for goal: {goal_id}")
        return task
