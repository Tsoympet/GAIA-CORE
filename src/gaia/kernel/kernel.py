"""Cognitive Kernel composition root and goal-driven execution API."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

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
        hydrate: bool = True,
    ) -> None:
        self.orchestrator = orchestrator
        self.store = store or KernelStore(":memory:")
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
    ) -> KernelRunResult:
        """Admit, execute, verify, and finalize one goal-driven run."""
        if goal_id is not None and resumed:
            goal = self.goals.require(goal_id)
            if goal.status != GoalStatus.INTERRUPTED:
                raise RuntimeError(
                    f"goal {goal_id} cannot resume from status {goal.status.value}"
                )
            goal.metadata = {
                **goal.metadata,
                **dict(metadata or {}),
                "resumed": True,
            }
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
            await self.events.emit(
                "goal.blocked",
                goal_id=goal.id,
                session_id=session_id,
                payload={"reasons": policy.reasons},
            )
            self.state.touch(KernelStatus.IDLE, last_goal_id=goal.id)
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=verification,
                budget=tracker.snapshot.model_dump(mode="json"),
                resumed=resumed,
                artifacts={"kernel_path": "policy_block"},
            )

        self.goals.activate(goal.id)
        self._persist_goal(self.goals.require(goal.id))
        self.state.active_goal_id = goal.id
        self.state.active_session_id = session_id
        self.state.touch(KernelStatus.RUNNING, last_goal_id=goal.id)
        await self.events.emit(
            "goal.activated",
            goal_id=goal.id,
            session_id=session_id,
            payload={"resumed": resumed},
        )

        started = perf_counter()
        interrupted = False
        try:
            if self.interrupts.is_interrupted(goal.id):
                raise InterruptedError("goal interrupted before execution")

            tracker.consume(steps=1)
            self._persist_budget(goal.id, tracker)
            await self.events.emit(
                "run.started",
                goal_id=goal.id,
                session_id=session_id,
                payload={"resumed": resumed},
            )
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
            self._persist_budget(goal.id, tracker)

            if self.interrupts.is_interrupted(goal.id):
                interrupted = True
                interrupt = self.interrupts.get(goal.id)
                reason = interrupt.reason if interrupt else "interrupted"
                self.goals.interrupt(goal.id, reason)
                self._persist_goal(self.goals.require(goal.id))
                self.interrupts.acknowledge(goal.id)
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
                return KernelRunResult(
                    goal=self.goals.require(goal.id),
                    response=response,
                    policy=policy,
                    verification=None,
                    budget=tracker.snapshot.model_dump(mode="json"),
                    interrupted=True,
                    resumed=resumed,
                    artifacts={"kernel_path": "interrupted"},
                )

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
                self.goals.complete(
                    goal.id,
                    metadata={"task_id": response.task_id},
                )
                self.state.verified_runs += 1
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
                self.state.failed_verifications += int(not verification.passed)
                await self.events.emit(
                    "goal.blocked",
                    goal_id=goal.id,
                    session_id=session_id,
                    payload={"source": "orchestrator"},
                )
            else:
                self.goals.fail(
                    goal.id,
                    "; ".join(verification.issues) or "verification failed",
                    metadata={"task_id": response.task_id},
                )
                self.state.failed_verifications += 1
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
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=verification,
                budget=tracker.snapshot.model_dump(mode="json"),
                interrupted=interrupted,
                resumed=resumed,
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
            self._persist_goal(self.goals.require(goal.id))
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
            await self.events.emit(
                "goal.budget_exceeded",
                goal_id=goal.id,
                session_id=session_id,
                payload={"error": str(exc)},
            )
            self.state.touch(KernelStatus.DEGRADED, last_goal_id=goal.id)
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=None,
                budget=tracker.snapshot.model_dump(mode="json"),
                interrupted=True,
                resumed=resumed,
                artifacts={"kernel_path": "budget_exceeded"},
            )
        except InterruptedError as exc:
            self.goals.interrupt(goal.id, str(exc))
            self._persist_goal(self.goals.require(goal.id))
            self.interrupts.acknowledge(goal.id)
            response = AggregatedResponse(
                task_id=goal.id,
                status="interrupted",
                answer=f"Task interrupted: {exc}",
                confidence=1.0,
                artifacts={"goal_id": goal.id},
            )
            await self.events.emit(
                "goal.interrupted",
                goal_id=goal.id,
                session_id=session_id,
                payload={"reason": str(exc), "phase": "before_run"},
            )
            self.state.touch(KernelStatus.INTERRUPTED, last_goal_id=goal.id)
            return KernelRunResult(
                goal=self.goals.require(goal.id),
                response=response,
                policy=policy,
                verification=None,
                budget=tracker.snapshot.model_dump(mode="json"),
                interrupted=True,
                resumed=resumed,
                artifacts={"kernel_path": "interrupted_before_run"},
            )
        except Exception as exc:
            self.goals.fail(goal.id, str(exc))
            self._persist_goal(self.goals.require(goal.id))
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
        """Resume an interrupted goal through another verified kernel run."""
        goal = self.goals.require(goal_id)
        if goal.status != GoalStatus.INTERRUPTED:
            raise RuntimeError(
                f"goal {goal_id} cannot resume from status {goal.status.value}"
            )
        # Clear residual interrupt latch before reactivation.
        self.interrupts.acknowledge(goal_id)
        if self.interrupts.is_interrupted(goal_id):
            self.interrupts.clear_global()
            self.interrupts.acknowledge(goal_id)

        resume_meta = {
            **dict(metadata or {}),
            "resume_of": goal_id,
            "previous_error": goal.error,
        }
        return await self.run(
            goal.objective,
            goal.session_id,
            goal.capabilities,
            budget=budget,
            metadata=resume_meta,
            goal_id=goal.id,
            resumed=True,
        )

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
            return cancelled
        cancelled = self.goals.cancel(goal_id, reason)
        self._persist_goal(cancelled)
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
        self.goals.remove(goal_id)
        self.contexts.release(goal_id)
        self._budgets.pop(goal_id, None)
        self.interrupts.acknowledge(goal_id)
        return removed

    def purge(self) -> dict[str, int]:
        """Purge all kernel goals, contexts, budgets, and events."""
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

    def _persist_goal(self, goal: Goal) -> None:
        self.store.upsert_goal(goal)

    def _persist_context(self, goal_id: str, session_id: str) -> None:
        snapshot = self.contexts.snapshot(goal_id)
        if snapshot:
            self.store.save_context(goal_id, session_id, snapshot)

    def _persist_budget(self, goal_id: str, tracker: ResourceBudgetTracker) -> None:
        self.store.save_budget(goal_id, tracker.snapshot.model_dump(mode="json"))


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
        hydrate=hydrate,
    )
