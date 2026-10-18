"""Cognitive Kernel composition root and goal-driven execution API."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from gaia.continuity.errors import ContinuityIntegrityError
from gaia.continuity.task_state import TaskState, TaskTransitionError
from gaia.core.event_bus import EventBus
from gaia.kernel.context_manager import ContextManager
from gaia.kernel.events import KernelEventLog
from gaia.kernel.goal_manager import Goal, GoalManager, GoalStatus
from gaia.kernel.interrupt_controller import InterruptController, InterruptKind
from gaia.kernel.policy_coordinator import PolicyCoordinator, PolicyGateDecision
from gaia.kernel.resource_budget import (
    BudgetExceededError,
    ResourceBudget,
    ResourceBudgetTracker,
)
from gaia.kernel.state import KernelState, KernelStatus
from gaia.kernel.store import KernelStore
from gaia.kernel.verification_coordinator import (
    VerificationCoordinator,
    VerificationReport,
)
from gaia.orchestrator.aggregator import AggregatedResponse
from gaia.orchestrator.engine import Orchestrator
from gaia.security.permission_manager import PermissionManager
from gaia.security.policy import SecurityPolicy

if TYPE_CHECKING:
    from gaia.continuity.journal import ContinuityJournal

_TERMINAL_GOALS: frozenset[GoalStatus] = frozenset(
    {
        GoalStatus.COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.CANCELLED,
        GoalStatus.BLOCKED,
    }
)


class KernelRunResult(BaseModel):
    """Full result of a kernel-managed task run."""

    goal: Goal
    response: AggregatedResponse
    policy: PolicyGateDecision
    verification: VerificationReport | None = None
    budget: dict[str, Any] = Field(default_factory=dict)
    interrupted: bool = False
    resumed: bool = False
    artifacts: dict[str, Any] = Field(default_factory=dict)


class CognitiveKernel:
    """Platform control plane wrapping the recovered orchestrator."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        security_policy: SecurityPolicy,
        permission_manager: PermissionManager,
        *,
        default_budget: ResourceBudget | None = None,
        goal_manager: GoalManager | None = None,
        context_manager: ContextManager | None = None,
        interrupt_controller: InterruptController | None = None,
        verification_coordinator: VerificationCoordinator | None = None,
        store: KernelStore | None = None,
        event_bus: EventBus | None = None,
        continuity: ContinuityJournal | None = None,
        hydrate: bool = True,
    ) -> None:
        self.orchestrator = orchestrator
        self.store = store or KernelStore(":memory:")
        self.continuity = continuity
        self.goals = goal_manager or GoalManager()
        self.contexts = context_manager or ContextManager(
            default_max_items=(default_budget or ResourceBudget()).max_context_items
        )
        self.interrupts = interrupt_controller or InterruptController()
        self.policy = PolicyCoordinator(security_policy, permission_manager)
        self.verification = verification_coordinator or VerificationCoordinator()
        self.default_budget = default_budget or ResourceBudget()
        self.event_bus = event_bus or EventBus()
        self.events = KernelEventLog(self.store, event_bus=self.event_bus)
        self.state = KernelState()
        self._budgets: dict[str, ResourceBudgetTracker] = {}
        if hydrate:
            self._hydrate_from_store()
            if self.continuity is not None:
                self.continuity.hydrate(self.goals, self.contexts)
                self.mirror_live_state()

    def _hydrate_from_store(self) -> None:
        """Load durable goals, contexts, and budgets into the live kernel."""
        goals = self.store.list_goals()
        self.goals.load(goals)
        for goal in goals:
            snapshot = self.store.get_context(goal.id)
            if snapshot is not None:
                self.contexts.restore(snapshot)
            budget = self.store.get_budget(goal.id)
            if budget is None:
                continue
            limits = budget.get("budget")
            if not isinstance(limits, dict):
                continue
            resource = ResourceBudget.model_validate(limits)
            tracker = ResourceBudgetTracker(resource)
            tracker.snapshot.steps_used = _as_int(budget.get("steps_used"))
            tracker.snapshot.model_calls_used = _as_int(budget.get("model_calls_used"))
            tracker.snapshot.tool_calls_used = _as_int(budget.get("tool_calls_used"))
            tracker.snapshot.wall_ms_used = _as_int(budget.get("wall_ms_used"))
            tracker.snapshot.context_items_used = _as_int(budget.get("context_items_used"))
            tracker.snapshot.memory_writes_used = _as_int(budget.get("memory_writes_used"))
            exhausted = budget.get("exhausted_resource")
            tracker.snapshot.exhausted_resource = (
                str(exhausted) if isinstance(exhausted, str) else None
            )
            self._budgets[goal.id] = tracker

    def status(self) -> KernelState:
        """Return a refreshed kernel status snapshot."""
        self.state.goals_tracked = self.goals.count()
        self.state.cancelled_goals = self.goals.count_by_status(GoalStatus.CANCELLED)
        self.state.interrupt_count = len(self.interrupts.history())
        self.state.details["persistence"] = self.store.status()
        if self.continuity is None:
            self.state.details["continuity"] = {
                "capability": "cognitive_continuity",
                "status": "unavailable",
                "durable": False,
            }
        else:
            self.state.details["continuity"] = {
                "capability": "cognitive_continuity",
                "status": self.continuity.capability_status(),
                "durable": True,
            }
        self.state.touch()
        return self.state

    async def run(
        self,
        objective: str,
        session_id: str,
        capabilities: Sequence[str] = (),
        *,
        budget: ResourceBudget | None = None,
        metadata: dict[str, Any] | None = None,
        goal_id: str | None = None,
        resumed: bool = False,
        from_waiting: bool = False,
    ) -> KernelRunResult:
        """Admit, execute, verify, and finalize one goal-driven run."""
        if goal_id is not None and (resumed or from_waiting):
            goal = self.goals.require(goal_id)
            if resumed:
                if goal.status != GoalStatus.INTERRUPTED:
                    raise RuntimeError(
                        f"goal {goal_id} cannot resume from status {goal.status.value}"
                    )
                goal.metadata = {
                    **goal.metadata,
                    **dict(metadata or {}),
                    "resumed": True,
                }
                self._track(
                    goal.id,
                    TaskState.CLASSIFIED,
                    "resume reclassifies the interrupted task; approvals are not restored",
                )
            else:
                if goal.status != GoalStatus.WAITING_FOR_USER:
                    raise RuntimeError(
                        f"goal {goal_id} cannot resume from status {goal.status.value}"
                    )
                goal.metadata = {**goal.metadata, **dict(metadata or {})}
                self._track(
                    goal.id,
                    TaskState.APPROVED_IF_REQUIRED,
                    "in-process approval accepted for the current action fingerprint",
                )
            self._persist_goal(goal)
        else:
            goal = self.goals.create(
                objective,
                session_id,
                capabilities=list(capabilities),
                metadata=metadata,
                goal_id=goal_id,
            )
            self._persist_goal(goal)
            self._track(goal.id, TaskState.CREATED, "goal created")

        await self.events.emit(
            "goal.created" if not resumed else "goal.resume_requested",
            goal_id=goal.id,
            session_id=session_id,
            payload={"objective": objective, "resumed": resumed},
        )

        policy = self.policy.admit_goal(objective)
        tracker = self._budgets.get(goal.id) or ResourceBudgetTracker(
            budget or self.default_budget
        )
        self._budgets[goal.id] = tracker
        self._persist_budget(goal.id, tracker)

        if self.contexts.get(goal.id) is None:
            self.contexts.bind(
                goal.id,
                session_id,
                max_items=tracker.budget.max_context_items,
            )
        self.contexts.put(
            goal.id,
            "objective",
            objective,
            tags=["kernel", "goal"],
        )
        self.contexts.put(
            goal.id,
            "policy",
            policy.model_dump(mode="json"),
            tags=["kernel", "policy"],
        )
        self._persist_context(goal.id, session_id)

        if not policy.allowed:
            self.goals.block(goal.id, "; ".join(policy.reasons) or "policy denied")
            self._persist_goal(self.goals.require(goal.id))
            response = self._terminal_response(
                goal.id,
                status="blocked",
                answer="Task blocked by GAIA Cognitive Kernel policy gate.",
                extra={"policy": policy.model_dump(mode="json")},
            )
            verification = self.verification.verify(response)
            self.state.failed_verifications += int(not verification.passed)
            self._track(goal.id, TaskState.BLOCKED, "policy denied")
            await self.events.emit(
                "goal.blocked",
                goal_id=goal.id,
                session_id=session_id,
                payload={"reasons": policy.reasons},
            )
            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            self._checkpoint(goal.id, "policy_block")
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                verification=verification,
                budget=tracker.snapshot.model_dump(mode="json"),
                resumed=resumed,
                artifacts={"kernel_path": "policy_block"},
            )

        if policy.requires_human_approval and not self._approval_live(goal):
            reason = "human approval required before execution"
            self.goals.wait(goal.id, reason)
            self._persist_goal(self.goals.require(goal.id))
            self._track(goal.id, TaskState.WAITING_FOR_USER, reason)
            response = self._terminal_response(
                goal.id,
                status="waiting_for_user",
                answer=(
                    "Task is waiting for human approval. "
                    "No reusable approval token was stored."
                ),
                extra={"policy": policy.model_dump(mode="json")},
            )
            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            self._checkpoint(goal.id, "waiting_for_user")
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                resumed=resumed,
                artifacts={"kernel_path": "waiting_for_user"},
            )

        task_state = self._task_state(goal.id)
        if task_state in {None, TaskState.CREATED, TaskState.INTERRUPTED}:
            self._track(goal.id, TaskState.CLASSIFIED, "policy admitted the goal")

        self.goals.activate(goal.id, from_waiting=from_waiting)
        self._persist_goal(self.goals.require(goal.id))
        self.state.active_goal_id = goal.id
        self.state.active_session_id = goal.session_id
        self.state.touch(KernelStatus.RUNNING, last_goal_id=goal.id)
        await self.events.emit(
            "goal.activated",
            goal_id=goal.id,
            session_id=session_id,
            payload={"resumed": resumed},
        )

        started = perf_counter()
        try:
            if self.interrupts.is_interrupted(goal.id):
                raise InterruptedError("goal interrupted before execution")

            tracker.consume(steps=1)
            self._persist_budget(goal.id, tracker)
            self._track(goal.id, TaskState.EXECUTING, "orchestrator execution started")
            await self.events.emit(
                "run.started",
                goal_id=goal.id,
                session_id=session_id,
                payload={"resumed": resumed},
            )
            response = await self.orchestrator.run(
                goal.objective,
                goal.session_id,
                goal.capabilities,
            )
            elapsed_ms = int((perf_counter() - started) * 1000)
            node_count_raw = response.artifacts.get("node_count", 1)
            node_count = node_count_raw if isinstance(node_count_raw, int) else 1
            working = self.contexts.get(goal.id)
            tracker.consume(
                steps=max(0, node_count - 1),
                model_calls=len(response.agents),
                wall_ms=elapsed_ms,
                context_items=working.size() if working is not None else 0,
                memory_writes=2,
            )
            self._persist_budget(goal.id, tracker)

            if self.interrupts.is_interrupted(goal.id):
                interrupt = self.interrupts.get(goal.id)
                reason = interrupt.reason if interrupt else "interrupted"
                self.goals.interrupt(goal.id, reason)
                self._persist_goal(self.goals.require(goal.id))
                self.interrupts.acknowledge(goal.id)
                self._track(goal.id, TaskState.INTERRUPTED, reason)
                response.status = "interrupted"
                response.artifacts = {
                    **response.artifacts,
                    "interrupt": interrupt.model_dump(mode="json") if interrupt else {},
                    "goal_id": goal.id,
                }
                await self.events.emit(
                    "goal.interrupted",
                    goal_id=goal.id,
                    session_id=session_id,
                    payload={"reason": reason},
                )
                self.state.touch(KernelStatus.INTERRUPTED, last_goal_id=goal.id)
                self._checkpoint(goal.id, "interrupted")
                return self._result(
                    goal.id,
                    response,
                    policy,
                    tracker,
                    interrupted=True,
                    resumed=resumed,
                    artifacts={"kernel_path": "interrupted"},
                )

            self._track(goal.id, TaskState.VERIFYING, "verification started")
            verification = self.verification.verify(response)
            self.contexts.put(
                goal.id,
                "verification",
                verification.model_dump(mode="json"),
                tags=["kernel", "verification"],
            )
            self._persist_context(goal.id, session_id)
            response.artifacts = {
                **response.artifacts,
                "goal_id": goal.id,
                "verification": verification.model_dump(mode="json"),
                "budget": tracker.snapshot.model_dump(mode="json"),
                "kernel": True,
                "resumed": resumed,
                "durable": True,
            }

            if verification.passed and response.status == "completed":
                self.goals.complete(goal.id, metadata={"task_id": response.task_id})
                self._track(goal.id, TaskState.COMPLETED, "verification passed")
                self.state.verified_runs += 1
                checkpoint_reason = "verified_run"
                await self.events.emit(
                    "goal.completed",
                    goal_id=goal.id,
                    session_id=session_id,
                    payload={"task_id": response.task_id, "resumed": resumed},
                )
            elif response.status == "blocked":
                self.goals.block(
                    goal.id,
                    "blocked by orchestrator security policy",
                    metadata={"task_id": response.task_id},
                )
                self._track(goal.id, TaskState.BLOCKED, "orchestrator blocked the run")
                self.state.failed_verifications += int(not verification.passed)
                checkpoint_reason = "orchestrator_blocked"
                await self.events.emit(
                    "goal.blocked",
                    goal_id=goal.id,
                    session_id=session_id,
                    payload={"source": "orchestrator"},
                )
            else:
                failure = "; ".join(verification.issues) or "verification failed"
                self.goals.fail(
                    goal.id,
                    failure,
                    metadata={"task_id": response.task_id},
                )
                self._track(goal.id, TaskState.FAILED, failure)
                self.state.failed_verifications += 1
                checkpoint_reason = "verification_failed"
                if response.status == "completed":
                    response.status = "failed_verification"
                await self.events.emit(
                    "goal.failed",
                    goal_id=goal.id,
                    session_id=session_id,
                    payload={"issues": verification.issues},
                )

            self._persist_goal(self.goals.require(goal.id))
            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            self._checkpoint(goal.id, checkpoint_reason)
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                verification=verification,
                budget=tracker.snapshot.model_dump(mode="json"),
                interrupted=False,
                resumed=resumed,
                artifacts={"kernel_path": "verified_run"},
            )

        except BudgetExceededError as exc:
            self.state.budget_violations += 1
            self.interrupts.request(goal.id, str(exc), kind=InterruptKind.BUDGET)
            self.goals.fail(goal.id, str(exc))
            self._persist_goal(self.goals.require(goal.id))
            self.interrupts.acknowledge(goal.id)
            self._track(goal.id, TaskState.FAILED, str(exc))
            response = self._terminal_response(
                goal.id,
                status="budget_exceeded",
                answer=f"Task stopped: {exc}",
                extra={"budget": tracker.snapshot.model_dump(mode="json")},
            )
            await self.events.emit(
                "goal.budget_exceeded",
                goal_id=goal.id,
                session_id=session_id,
                payload={"error": str(exc)},
            )
            self.state.touch(KernelStatus.DEGRADED, last_goal_id=goal.id)
            self._checkpoint(goal.id, "budget_exceeded")
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                interrupted=True,
                resumed=resumed,
                artifacts={"kernel_path": "budget_exceeded"},
            )
        except InterruptedError as exc:
            self.goals.interrupt(goal.id, str(exc))
            self._persist_goal(self.goals.require(goal.id))
            self.interrupts.acknowledge(goal.id)
            self._track(goal.id, TaskState.INTERRUPTED, str(exc))
            response = self._terminal_response(
                goal.id,
                status="interrupted",
                answer=f"Task interrupted: {exc}",
            )
            await self.events.emit(
                "goal.interrupted",
                goal_id=goal.id,
                session_id=session_id,
                payload={"reason": str(exc), "phase": "before_run"},
            )
            self.state.touch(KernelStatus.INTERRUPTED, last_goal_id=goal.id)
            self._checkpoint(goal.id, "interrupted_before_run")
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                interrupted=True,
                resumed=resumed,
                artifacts={"kernel_path": "interrupted_before_run"},
            )
        except Exception as exc:
            self.goals.fail(goal.id, str(exc))
            self._persist_goal(self.goals.require(goal.id))
            self._fail_open(goal.id, str(exc))
            await self.events.emit(
                "goal.failed",
                goal_id=goal.id,
                session_id=session_id,
                payload={"error": str(exc)},
            )
            self.state.touch(KernelStatus.DEGRADED, last_goal_id=goal.id, error=str(exc))
            raise
        finally:
            self.state.active_goal_id = None

    async def resume(
        self,
        goal_id: str,
        *,
        budget: ResourceBudget | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KernelRunResult:
        """Resume an interrupted goal, or a waiting goal with a live approval.

        KernelStore resume re-runs an interrupted goal. When the continuity
        journal is configured, a waiting goal runs only if this process holds
        a live grant. Stored approval events are not reusable.
        """
        goal = self.goals.require(goal_id)
        if self.continuity is not None:
            try:
                self.continuity.assert_resume_current()
            except ContinuityIntegrityError as exc:
                raise RuntimeError(str(exc)) from exc
        resume_meta = {
            **dict(metadata or {}),
            "resume_of": goal_id,
            "previous_error": goal.error,
        }
        if goal.status == GoalStatus.INTERRUPTED:
            self.interrupts.acknowledge(goal_id)
            if self.interrupts.is_interrupted(goal_id):
                self.interrupts.clear_global()
                self.interrupts.acknowledge(goal_id)
            return await self.run(
                goal.objective,
                goal.session_id,
                goal.capabilities,
                budget=budget,
                metadata=resume_meta,
                goal_id=goal.id,
                resumed=True,
            )
        if goal.status == GoalStatus.WAITING_FOR_USER:
            if not self._approval_live(goal):
                raise RuntimeError(
                    "waiting task has no live in-process approval; "
                    "stored approval events are not reusable"
                )
            return await self.run(
                goal.objective,
                goal.session_id,
                goal.capabilities,
                budget=budget,
                metadata=resume_meta,
                goal_id=goal.id,
                from_waiting=True,
            )
        raise RuntimeError(
            f"goal {goal_id} cannot resume from status {goal.status.value}"
        )

    def grant_approval(self, goal_id: str, approver: str) -> Goal:
        """Grant a process-local approval for a waiting goal."""
        if self.continuity is None:
            raise RuntimeError("approval requires cognitive continuity to be configured")
        goal = self.goals.require(goal_id)
        self.continuity.grant(goal, approver)
        return goal

    def deny_approval(self, goal_id: str, approver: str, reason: str) -> Goal:
        """Deny a waiting goal and persist the blocked state."""
        if self.continuity is None:
            raise RuntimeError("approval requires cognitive continuity to be configured")
        goal = self.goals.require(goal_id)
        self.continuity.deny(goal, approver)
        blocked = self.goals.block(goal_id, reason)
        self._persist_goal(blocked)
        self._track(goal_id, TaskState.BLOCKED, reason)
        self._checkpoint(goal_id, "approval_denied")
        return blocked

    def cancel_goal(self, goal_id: str, reason: str = "operator cancel") -> Goal:
        """Request cancellation for an active goal, or cancel a non-running goal."""
        goal = self.goals.require(goal_id)
        if goal.status == GoalStatus.ACTIVE:
            self.interrupts.request(
                goal_id,
                reason,
                kind=InterruptKind.OPERATOR,
            )
            return goal
        if goal.status == GoalStatus.INTERRUPTED:
            cancelled = self.goals.cancel(goal_id, reason)
            self._persist_goal(cancelled)
            self._track(goal_id, TaskState.CANCELLED, reason)
            self._checkpoint(goal_id, "cancelled")
            return cancelled
        cancelled = self.goals.cancel(goal_id, reason)
        self._persist_goal(cancelled)
        self._track(goal_id, TaskState.CANCELLED, reason)
        self._checkpoint(goal_id, "cancelled")
        return cancelled

    def get_budget(self, goal_id: str) -> dict[str, Any] | None:
        """Return budget snapshot for a goal, preferring live then durable state."""
        tracker = self._budgets.get(goal_id)
        if tracker is not None:
            return tracker.snapshot.model_dump(mode="json")
        return self.store.get_budget(goal_id)

    def delete_goal(self, goal_id: str) -> bool:
        """Delete a goal and all durable derivatives from live and stored state."""
        removed = self.store.delete_goal(goal_id)
        if self.continuity is not None:
            self.continuity.store.delete_goal(goal_id, "kernel delete")
        self.goals.remove(goal_id)
        self.contexts.release(goal_id)
        self._budgets.pop(goal_id, None)
        self.interrupts.acknowledge(goal_id)
        return removed

    def purge(self) -> dict[str, int]:
        """Purge all kernel goals, contexts, budgets, and events."""
        if self.continuity is not None:
            for goal in self.continuity.store.list_goals():
                self.continuity.store.delete_goal(goal.id, "kernel purge")
        counts = self.store.purge()
        self.goals.clear()
        self.contexts.clear()
        self._budgets.clear()
        self.state.touch(KernelStatus.IDLE, purged=True)
        return counts

    def restore(self, source: Path | str) -> None:
        """Restore durable state from backup and rehydrate the live kernel."""
        self.store.restore(source)
        self.goals.clear()
        self.contexts.clear()
        self._budgets.clear()
        self._hydrate_from_store()
        self.state.touch(KernelStatus.IDLE, restored=True)

    def backup(self, destination: Path | str) -> Path:
        """Create a portable backup of kernel durable state."""
        return self.store.backup(destination)

    def mirror_live_state(self, *, drop_missing: bool = False) -> None:
        """Write live goals and contexts back into KernelStore.

        Continuity recovery overlays the live managers. This copy keeps the
        live store aligned with that overlay. Checkpoints stay in the journal.
        """
        live_ids = {goal.id for goal in self.goals.list_goals()}
        if drop_missing:
            for stored in self.store.list_goals():
                if stored.id not in live_ids:
                    self.store.delete_goal(stored.id)
                    self._budgets.pop(stored.id, None)
        for goal in self.goals.list_goals():
            self._persist_goal(goal)
            context = self.contexts.get(goal.id)
            if context is None:
                continue
            self.store.save_context(
                goal.id,
                context.session_id,
                self.contexts.snapshot(goal.id),
            )

    def _persist_goal(self, goal: Goal) -> None:
        self.store.upsert_goal(goal)

    def _persist_context(self, goal_id: str, session_id: str) -> None:
        self._record_continuity_context(goal_id)
        snapshot = self.contexts.snapshot(goal_id)
        if snapshot:
            self.store.save_context(goal_id, session_id, snapshot)

    def _persist_budget(self, goal_id: str, tracker: ResourceBudgetTracker) -> None:
        self.store.save_budget(goal_id, tracker.snapshot.model_dump(mode="json"))

    def _task_state(self, goal_id: str) -> TaskState | None:
        if self.continuity is None:
            return None
        task = self.continuity.store.get_task_by_goal(goal_id)
        if task is None:
            return None
        return task.state

    def _approval_live(self, goal: Goal) -> bool:
        if self.continuity is None:
            return False
        task = self.continuity.store.get_task_by_goal(goal.id)
        if task is None:
            return False
        return self.continuity.approval_is_live(task.task_id, task.action_fingerprint)

    def _track(self, goal_id: str, state: TaskState, reason: str) -> None:
        if self.continuity is None:
            return
        goal = self.goals.get(goal_id)
        if goal is None:
            return
        self.continuity.record(goal, state, reason)
        self._persist_goal(goal)
        self._record_continuity_context(goal_id)

    def _record_continuity_context(self, goal_id: str) -> None:
        if self.continuity is None:
            return
        context = self.contexts.get(goal_id)
        if context is not None:
            self.continuity.record_context(context)

    def _checkpoint(self, goal_id: str, reason: str) -> None:
        if self.continuity is None:
            return
        tracker = self._budgets.get(goal_id)
        if tracker is not None:
            self.continuity.store.update_task_budget(
                goal_id,
                tracker.snapshot.model_dump(mode="json"),
            )
        self.continuity.publish(reason=reason, kernel_id=self.state.kernel_id)

    def _fail_open(self, goal_id: str, reason: str) -> None:
        goal = self.goals.get(goal_id)
        if goal is None:
            return
        if goal.status not in _TERMINAL_GOALS:
            try:
                self.goals.fail(goal_id, reason)
            except RuntimeError:
                return
        try:
            self._track(goal_id, TaskState.FAILED, reason)
        except TaskTransitionError:
            return
        try:
            self._checkpoint(goal_id, "execution_failed")
        except Exception:  # noqa: BLE001
            return

    def _terminal_response(
        self,
        goal_id: str,
        *,
        status: str,
        answer: str,
        extra: dict[str, Any] | None = None,
    ) -> AggregatedResponse:
        artifacts: dict[str, Any] = {"goal_id": goal_id}
        if extra:
            artifacts.update(extra)
        return AggregatedResponse(
            task_id=goal_id,
            status=status,
            answer=answer,
            confidence=1.0,
            artifacts=artifacts,
        )

    def _result(
        self,
        goal_id: str,
        response: AggregatedResponse,
        policy: PolicyGateDecision,
        tracker: ResourceBudgetTracker,
        *,
        verification: VerificationReport | None = None,
        interrupted: bool = False,
        resumed: bool = False,
        budget: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> KernelRunResult:
        return KernelRunResult(
            goal=self.goals.require(goal_id),
            response=response,
            policy=policy,
            verification=verification,
            budget=budget if budget is not None else tracker.snapshot.model_dump(mode="json"),
            interrupted=interrupted,
            resumed=resumed,
            artifacts=dict(artifacts or {}),
        )


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def create_cognitive_kernel(
    orchestrator: Orchestrator,
    security_policy: SecurityPolicy,
    permission_manager: PermissionManager,
    *,
    default_budget: ResourceBudget | None = None,
    kernel_db_path: Path | str = ":memory:",
    event_bus: EventBus | None = None,
    continuity: ContinuityJournal | None = None,
    hydrate: bool = True,
) -> CognitiveKernel:
    """Create the default Cognitive Kernel over the recovered orchestrator."""
    return CognitiveKernel(
        orchestrator=orchestrator,
        security_policy=security_policy,
        permission_manager=permission_manager,
        default_budget=default_budget,
        store=KernelStore(kernel_db_path),
        event_bus=event_bus,
        continuity=continuity,
        hydrate=hydrate,
    )
