"""Cognitive Kernel composition root and goal-driven execution API."""

from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from gaia.continuity.task_state import TaskState, TaskTransitionError
from gaia.kernel.context_manager import ContextManager
from gaia.kernel.goal_manager import Goal, GoalManager, GoalStatus
from gaia.kernel.interrupt_controller import InterruptController, InterruptKind
from gaia.kernel.policy_coordinator import PolicyCoordinator, PolicyGateDecision
from gaia.kernel.resource_budget import (
    BudgetExceededError,
    ResourceBudget,
    ResourceBudgetTracker,
)
from gaia.kernel.state import KernelState, KernelStatus
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
        continuity: ContinuityJournal | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.goals = goal_manager or GoalManager()
        self.contexts = context_manager or ContextManager(
            default_max_items=(default_budget or ResourceBudget()).max_context_items
        )
        self.interrupts = interrupt_controller or InterruptController()
        self.policy = PolicyCoordinator(security_policy, permission_manager)
        self.verification = verification_coordinator or VerificationCoordinator()
        self.default_budget = default_budget or ResourceBudget()
        self.continuity = continuity
        self.state = KernelState()
        self._budgets: dict[str, ResourceBudgetTracker] = {}
        if continuity is not None:
            continuity.hydrate(self.goals, self.contexts)

    def status(self) -> KernelState:
        """Return a refreshed kernel status snapshot."""
        self.state.goals_tracked = self.goals.count()
        self.state.cancelled_goals = self.goals.count_by_status(GoalStatus.CANCELLED)
        self.state.interrupt_count = len(self.interrupts.history())
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
    ) -> KernelRunResult:
        """Admit, execute, verify, and finalize one goal-driven run."""
        goal = self.goals.create(
            objective,
            session_id,
            capabilities=list(capabilities),
            metadata=metadata,
        )
        self._track(goal.id, TaskState.CREATED, "goal created")
        return await self._execute(goal, budget)

    async def resume(
        self,
        goal_id: str,
        *,
        budget: ResourceBudget | None = None,
    ) -> KernelRunResult:
        """Re-evaluate and continue an interrupted or approved waiting goal.

        Resume never reuses an approval from a previous process. A waiting goal
        runs only when this process holds a live grant for the same action.
        """
        if self.continuity is None:
            raise RuntimeError("resume requires cognitive continuity to be configured")
        goal = self.goals.require(goal_id)
        task = self.continuity.store.get_task_by_goal(goal_id)
        if task is None:
            raise RuntimeError(f"goal {goal_id} has no continuity task record")
        if goal.status is GoalStatus.INTERRUPTED or task.state is TaskState.INTERRUPTED:
            self._track(
                goal.id,
                TaskState.CLASSIFIED,
                "resume reclassifies the interrupted task; approvals are not restored",
            )
            return await self._execute(goal, budget)
        if (
            goal.status is GoalStatus.WAITING_FOR_USER
            or task.state is TaskState.WAITING_FOR_USER
        ):
            if not self._approval_live(goal):
                raise RuntimeError(
                    "waiting task has no live in-process approval; "
                    "stored approval events are not reusable"
                )
            self._track(
                goal.id,
                TaskState.APPROVED_IF_REQUIRED,
                "in-process approval accepted for the current action fingerprint",
            )
            return await self._execute(goal, budget)
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
        self._track(goal_id, TaskState.BLOCKED, reason)
        self._checkpoint(goal_id, "approval_denied")
        return blocked

    async def _execute(
        self,
        goal: Goal,
        budget: ResourceBudget | None,
    ) -> KernelRunResult:
        policy = self.policy.admit_goal(goal.objective)
        tracker = ResourceBudgetTracker(budget or self.default_budget)
        self._budgets[goal.id] = tracker
        self.contexts.bind(
            goal.id,
            goal.session_id,
            max_items=tracker.budget.max_context_items,
        )
        self.contexts.put(goal.id, "objective", goal.objective, tags=["kernel", "goal"])
        self.contexts.put(
            goal.id,
            "policy",
            policy.model_dump(mode="json"),
            tags=["kernel", "policy"],
        )
        self._persist_context(goal.id)

        if not policy.allowed:
            self.goals.block(goal.id, "; ".join(policy.reasons) or "policy denied")
            self._track(goal.id, TaskState.BLOCKED, "policy denied")
            response = self._terminal_response(
                goal.id,
                status="blocked",
                answer="Task blocked by GAIA Cognitive Kernel policy gate.",
                extra={"policy": policy.model_dump(mode="json")},
            )
            verification = self.verification.verify(response)
            self.state.failed_verifications += int(not verification.passed)
            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            self._checkpoint(goal.id, "policy_block")
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                verification=verification,
                kernel_path="policy_block",
            )

        if policy.requires_human_approval and not self._approval_live(goal):
            reason = "human approval required before execution"
            self.goals.wait(goal.id, reason)
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
                kernel_path="waiting_for_user",
            )

        state = self._task_state(goal.id)
        if state in {None, TaskState.CREATED, TaskState.INTERRUPTED}:
            self._track(goal.id, TaskState.CLASSIFIED, "policy admitted the goal")

        self.goals.activate(
            goal.id,
            from_waiting=goal.status is GoalStatus.WAITING_FOR_USER,
        )
        self.state.active_goal_id = goal.id
        self.state.active_session_id = goal.session_id
        self.state.touch(KernelStatus.RUNNING, last_goal_id=goal.id)

        started = perf_counter()
        try:
            if self.interrupts.is_interrupted(goal.id):
                raise InterruptedError("goal interrupted before execution")

            tracker.consume(steps=1)
            self._track(goal.id, TaskState.EXECUTING, "orchestrator execution started")
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

            if self.interrupts.is_interrupted(goal.id):
                interrupt = self.interrupts.get(goal.id)
                reason = interrupt.reason if interrupt else "interrupted"
                self.goals.interrupt(goal.id, reason)
                self.interrupts.acknowledge(goal.id)
                self._track(goal.id, TaskState.INTERRUPTED, reason)
                response.status = "interrupted"
                response.artifacts = {
                    **response.artifacts,
                    "interrupt": interrupt.model_dump(mode="json") if interrupt else {},
                    "goal_id": goal.id,
                }
                self.state.touch(KernelStatus.INTERRUPTED, last_goal_id=goal.id)
                self._checkpoint(goal.id, "interrupted")
                return self._result(
                    goal.id,
                    response,
                    policy,
                    tracker,
                    interrupted=True,
                    kernel_path="interrupted",
                )

            self._track(goal.id, TaskState.VERIFYING, "verification started")
            verification = self.verification.verify(response)
            self.contexts.put(
                goal.id,
                "verification",
                verification.model_dump(mode="json"),
                tags=["kernel", "verification"],
            )
            self._persist_context(goal.id)
            response.artifacts = {
                **response.artifacts,
                "goal_id": goal.id,
                "verification": verification.model_dump(mode="json"),
                "budget": tracker.snapshot.model_dump(mode="json"),
                "kernel": True,
            }

            if verification.passed and response.status == "completed":
                self.goals.complete(goal.id, metadata={"task_id": response.task_id})
                self._track(goal.id, TaskState.COMPLETED, "verification passed")
                self.state.verified_runs += 1
                checkpoint_reason = "verified_run"
            elif response.status == "blocked":
                self.goals.block(
                    goal.id,
                    "blocked by orchestrator security policy",
                    metadata={"task_id": response.task_id},
                )
                self._track(goal.id, TaskState.BLOCKED, "orchestrator blocked the run")
                self.state.failed_verifications += int(not verification.passed)
                checkpoint_reason = "orchestrator_blocked"
            else:
                failure = "; ".join(verification.issues) or "verification failed"
                self.goals.fail(
                    goal.id,
                    failure,
                    metadata={"task_id": response.task_id},
                )
                self._track(goal.id, TaskState.FAILED, failure)
                self.state.failed_verifications += 1
                if response.status == "completed":
                    response.status = "failed_verification"
                checkpoint_reason = "verification_failed"

            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            self._checkpoint(goal.id, checkpoint_reason)
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                verification=verification,
                kernel_path="verified_run",
            )

        except BudgetExceededError as exc:
            self.state.budget_violations += 1
            self.interrupts.request(goal.id, str(exc), kind=InterruptKind.BUDGET)
            self.goals.fail(goal.id, str(exc))
            self.interrupts.acknowledge(goal.id)
            self._track(goal.id, TaskState.FAILED, str(exc))
            response = self._terminal_response(
                goal.id,
                status="budget_exceeded",
                answer=f"Task stopped: {exc}",
                extra={"budget": tracker.snapshot.model_dump(mode="json")},
            )
            self.state.touch(KernelStatus.DEGRADED, last_goal_id=goal.id)
            self._checkpoint(goal.id, "budget_exceeded")
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                interrupted=True,
                kernel_path="budget_exceeded",
            )
        except InterruptedError as exc:
            self.goals.interrupt(goal.id, str(exc))
            self.interrupts.acknowledge(goal.id)
            self._track(goal.id, TaskState.INTERRUPTED, str(exc))
            response = self._terminal_response(
                goal.id,
                status="interrupted",
                answer=f"Task interrupted: {exc}",
            )
            self.state.touch(KernelStatus.INTERRUPTED, last_goal_id=goal.id)
            self._checkpoint(goal.id, "interrupted_before_run")
            return self._result(
                goal.id,
                response,
                policy,
                tracker,
                interrupted=True,
                kernel_path="interrupted_before_run",
            )
        except Exception as exc:
            self._fail_open(goal.id, str(exc))
            self.state.touch(KernelStatus.DEGRADED, last_goal_id=goal.id, error=str(exc))
            raise
        finally:
            self.state.active_goal_id = None

    def cancel_goal(self, goal_id: str, reason: str = "operator cancel") -> Goal:
        """Request cancellation for an active goal, or cancel a non-running goal."""
        goal = self.goals.require(goal_id)
        if goal.status == GoalStatus.ACTIVE:
            self.interrupts.request(goal_id, reason, kind=InterruptKind.OPERATOR)
            return goal
        if goal.status == GoalStatus.INTERRUPTED:
            cancelled = self.goals.cancel(goal_id, reason)
            self._track(goal_id, TaskState.CANCELLED, reason)
            self._checkpoint(goal_id, "cancelled")
            return cancelled
        cancelled = self.goals.cancel(goal_id, reason)
        self._track(goal_id, TaskState.CANCELLED, reason)
        self._checkpoint(goal_id, "cancelled")
        return cancelled

    def get_budget(self, goal_id: str) -> dict[str, Any] | None:
        """Return budget snapshot for a goal, if tracked."""
        tracker = self._budgets.get(goal_id)
        if tracker is None:
            return None
        return tracker.snapshot.model_dump(mode="json")

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
        self._persist_context(goal_id)

    def _persist_context(self, goal_id: str) -> None:
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
        except Exception:
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
        kernel_path: str,
    ) -> KernelRunResult:
        return KernelRunResult(
            goal=self.goals.require(goal_id),
            response=response,
            policy=policy,
            verification=verification,
            budget=tracker.snapshot.model_dump(mode="json"),
            interrupted=interrupted,
            artifacts={"kernel_path": kernel_path},
        )


def create_cognitive_kernel(
    orchestrator: Orchestrator,
    security_policy: SecurityPolicy,
    permission_manager: PermissionManager,
    *,
    default_budget: ResourceBudget | None = None,
    continuity: ContinuityJournal | None = None,
) -> CognitiveKernel:
    """Create the default Cognitive Kernel over the recovered orchestrator."""
    return CognitiveKernel(
        orchestrator=orchestrator,
        security_policy=security_policy,
        permission_manager=permission_manager,
        default_budget=default_budget,
        continuity=continuity,
    )
