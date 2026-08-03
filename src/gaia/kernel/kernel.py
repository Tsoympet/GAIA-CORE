"""Cognitive Kernel composition root and goal-driven execution API."""

from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

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
        self.state = KernelState()
        self._budgets: dict[str, ResourceBudgetTracker] = {}

    def status(self) -> KernelState:
        """Return a refreshed kernel status snapshot."""
        self.state.goals_tracked = self.goals.count()
        self.state.cancelled_goals = self.goals.count_by_status(GoalStatus.CANCELLED)
        self.state.interrupt_count = len(self.interrupts.history())
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
        policy = self.policy.admit_goal(objective)
        tracker = ResourceBudgetTracker(budget or self.default_budget)
        self._budgets[goal.id] = tracker

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

        if not policy.allowed:
            self.goals.block(goal.id, "; ".join(policy.reasons) or "policy denied")
            response = AggregatedResponse(
                task_id=goal.id,
                status="blocked",
                answer="Task blocked by GAIA Cognitive Kernel policy gate.",
                confidence=1.0,
                artifacts={
                    "policy": policy.model_dump(mode="json"),
                    "goal_id": goal.id,
                },
            )
            verification = self.verification.verify(response)
            self.state.failed_verifications += int(not verification.passed)
            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=verification,
                budget=tracker.snapshot.model_dump(mode="json"),
                artifacts={"kernel_path": "policy_block"},
            )

        self.goals.activate(goal.id)
        self.state.active_goal_id = goal.id
        self.state.active_session_id = session_id
        self.state.touch(KernelStatus.RUNNING, last_goal_id=goal.id)

        started = perf_counter()
        interrupted = False
        try:
            if self.interrupts.is_interrupted(goal.id):
                raise InterruptedError("goal interrupted before execution")

            tracker.consume(steps=1)
            response = await self.orchestrator.run(
                objective,
                session_id,
                capabilities,
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
                interrupted = True
                interrupt = self.interrupts.get(goal.id)
                reason = interrupt.reason if interrupt else "interrupted"
                self.goals.interrupt(goal.id, reason)
                self.interrupts.acknowledge(goal.id)
                response.status = "interrupted"
                response.artifacts = {
                    **response.artifacts,
                    "interrupt": interrupt.model_dump(mode="json") if interrupt else {},
                    "goal_id": goal.id,
                }
                self.state.touch(KernelStatus.INTERRUPTED, last_goal_id=goal.id)
                return KernelRunResult(
                    goal=self.goals.require(goal.id),
                    response=response,
                    policy=policy,
                    verification=None,
                    budget=tracker.snapshot.model_dump(mode="json"),
                    interrupted=True,
                    artifacts={"kernel_path": "interrupted"},
                )

            verification = self.verification.verify(response)
            self.contexts.put(
                goal.id,
                "verification",
                verification.model_dump(mode="json"),
                tags=["kernel", "verification"],
            )
            response.artifacts = {
                **response.artifacts,
                "goal_id": goal.id,
                "verification": verification.model_dump(mode="json"),
                "budget": tracker.snapshot.model_dump(mode="json"),
                "kernel": True,
            }

            if verification.passed and response.status == "completed":
                self.goals.complete(
                    goal.id,
                    metadata={"task_id": response.task_id},
                )
                self.state.verified_runs += 1
            elif response.status == "blocked":
                self.goals.block(
                    goal.id,
                    "blocked by orchestrator security policy",
                    metadata={"task_id": response.task_id},
                )
                self.state.failed_verifications += int(not verification.passed)
            else:
                self.goals.fail(
                    goal.id,
                    "; ".join(verification.issues) or "verification failed",
                    metadata={"task_id": response.task_id},
                )
                self.state.failed_verifications += 1
                if response.status == "completed":
                    response.status = "failed_verification"

            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=verification,
                budget=tracker.snapshot.model_dump(mode="json"),
                interrupted=interrupted,
                artifacts={"kernel_path": "verified_run"},
            )

        except BudgetExceededError as exc:
            self.state.budget_violations += 1
            self.interrupts.request(
                goal.id,
                str(exc),
                kind=InterruptKind.BUDGET,
            )
            self.goals.fail(goal.id, str(exc))
            self.interrupts.acknowledge(goal.id)
            response = AggregatedResponse(
                task_id=goal.id,
                status="budget_exceeded",
                answer=f"Task stopped: {exc}",
                confidence=1.0,
                artifacts={
                    "goal_id": goal.id,
                    "budget": tracker.snapshot.model_dump(mode="json"),
                },
            )
            self.state.touch(KernelStatus.DEGRADED, last_goal_id=goal.id)
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=None,
                budget=tracker.snapshot.model_dump(mode="json"),
                interrupted=True,
                artifacts={"kernel_path": "budget_exceeded"},
            )
        except InterruptedError as exc:
            self.goals.interrupt(goal.id, str(exc))
            self.interrupts.acknowledge(goal.id)
            response = AggregatedResponse(
                task_id=goal.id,
                status="interrupted",
                answer=f"Task interrupted: {exc}",
                confidence=1.0,
                artifacts={"goal_id": goal.id},
            )
            self.state.touch(KernelStatus.INTERRUPTED, last_goal_id=goal.id)
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=None,
                budget=tracker.snapshot.model_dump(mode="json"),
                interrupted=True,
                artifacts={"kernel_path": "interrupted_before_run"},
            )
        except Exception as exc:
            self.goals.fail(goal.id, str(exc))
            self.state.touch(KernelStatus.DEGRADED, last_goal_id=goal.id, error=str(exc))
            raise
        finally:
            self.state.active_goal_id = None

    def cancel_goal(self, goal_id: str, reason: str = "operator cancel") -> Goal:
        """Request cancellation for an active goal, or cancel a non-running goal."""
        goal = self.goals.require(goal_id)
        if goal.status == GoalStatus.ACTIVE:
            self.interrupts.request(
                goal_id,
                reason,
                kind=InterruptKind.OPERATOR,
            )
            # Status transitions to interrupted when the run loop observes the latch.
            return goal
        if goal.status == GoalStatus.INTERRUPTED:
            return self.goals.cancel(goal_id, reason)
        return self.goals.cancel(goal_id, reason)

    def get_budget(self, goal_id: str) -> dict[str, Any] | None:
        """Return budget snapshot for a goal, if tracked."""
        tracker = self._budgets.get(goal_id)
        if tracker is None:
            return None
        return tracker.snapshot.model_dump(mode="json")


def create_cognitive_kernel(
    orchestrator: Orchestrator,
    security_policy: SecurityPolicy,
    permission_manager: PermissionManager,
    *,
    default_budget: ResourceBudget | None = None,
) -> CognitiveKernel:
    """Create the default Cognitive Kernel over the recovered orchestrator."""
    return CognitiveKernel(
        orchestrator=orchestrator,
        security_policy=security_policy,
        permission_manager=permission_manager,
        default_budget=default_budget,
    )
