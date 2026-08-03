"""Cognitive Kernel coordination and execution governance."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from gaia.kernel.cancellation import CancellationRegistry
from gaia.kernel.errors import (
    KernelBudgetError,
    KernelCancelledError,
    KernelTimeoutError,
)
from gaia.kernel.goals import GoalManager
from gaia.kernel.models import (
    ExecutionStatus,
    GoalStatus,
    KernelExecution,
    KernelStatus,
    ResourceBudget,
    ResourceUsage,
)
from gaia.kernel.verification import VerificationEngine
from gaia.orchestrator.aggregator import AggregatedResponse

ExecutionOperation = Callable[[], Coroutine[Any, Any, AggregatedResponse]]


class CognitiveKernel:
    """Permanent governance layer around model and agent execution."""

    def __init__(
        self,
        *,
        goals: GoalManager | None = None,
        cancellations: CancellationRegistry | None = None,
        verifier: VerificationEngine | None = None,
    ) -> None:
        self.goals = goals or GoalManager()
        self.cancellations = cancellations or CancellationRegistry()
        self.verifier = verifier or VerificationEngine()
        self._executions: dict[str, KernelExecution] = {}

    def status(self) -> KernelStatus:
        executions = list(self._executions.values())
        goals = self.goals.list()
        return KernelStatus(
            goals=len(goals),
            active_goals=sum(
                goal.status == GoalStatus.ACTIVE for goal in goals
            ),
            executions=len(executions),
            active_executions=sum(
                execution.status == ExecutionStatus.RUNNING
                for execution in executions
            ),
            cancellation_requests=self.cancellations.requested_count(),
        )

    def begin_execution(
        self,
        *,
        objective: str,
        session_id: str,
        capabilities: list[str],
        goal_id: str | None = None,
        budget: ResourceBudget | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KernelExecution:
        normalized = objective.strip()
        if not normalized:
            raise ValueError("kernel objective must not be empty")
        execution_budget = budget or ResourceBudget()
        expected_steps = max(1, len(capabilities))
        if (
            execution_budget.max_steps is not None
            and expected_steps > execution_budget.max_steps
        ):
            raise KernelBudgetError(
                f"planned steps {expected_steps} exceed budget "
                f"{execution_budget.max_steps}"
            )

        if goal_id is None:
            goal = self.goals.create(
                normalized,
                metadata={"auto_created": True, **(metadata or {})},
            )
            goal_id = goal.goal_id
        else:
            self.goals.get(goal_id)

        goal = self.goals.get(goal_id)
        if goal.status == GoalStatus.PLANNED:
            self.goals.activate(goal_id)
        elif goal.status != GoalStatus.ACTIVE:
            raise ValueError(
                f"goal {goal_id} is not executable from {goal.status.value}"
            )

        execution = KernelExecution(
            session_id=session_id,
            objective=normalized,
            capabilities=list(dict.fromkeys(capabilities)),
            goal_id=goal_id,
            budget=execution_budget,
        )
        self._executions[execution.execution_id] = execution
        self.cancellations.register(execution.execution_id)
        return execution

    def get_execution(self, execution_id: str) -> KernelExecution:
        try:
            return self._executions[execution_id]
        except KeyError as exc:
            raise KeyError(
                f"kernel execution is not registered: {execution_id}"
            ) from exc

    def list_executions(
        self,
        status: ExecutionStatus | None = None,
    ) -> list[KernelExecution]:
        executions = list(self._executions.values())
        if status is not None:
            executions = [
                execution
                for execution in executions
                if execution.status == status
            ]
        return sorted(
            executions,
            key=lambda execution: (
                execution.created_at,
                execution.execution_id,
            ),
        )

    def request_cancellation(self, execution_id: str, reason: str) -> None:
        execution = self.get_execution(execution_id)
        if execution.status not in {
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
        }:
            raise ValueError(
                f"execution {execution_id} cannot be cancelled from "
                f"{execution.status.value}"
            )
        self.cancellations.request(execution_id, reason)

    async def run_guarded(
        self,
        execution_id: str,
        operation: ExecutionOperation,
    ) -> AggregatedResponse:
        execution = self.get_execution(execution_id)
        if execution.status != ExecutionStatus.PENDING:
            raise ValueError(
                f"execution {execution_id} is not pending"
            )
        started = monotonic()
        self._update_execution(
            execution_id,
            {
                "status": ExecutionStatus.RUNNING,
                "started_at": datetime.now(UTC),
            },
        )
        work_task: asyncio.Task[AggregatedResponse] = asyncio.create_task(
            operation()
        )
        cancel_task: asyncio.Task[bool] = asyncio.create_task(
            self.cancellations.get(execution_id).wait()
        )

        done, _ = await asyncio.wait(
            {work_task, cancel_task},
            timeout=execution.budget.max_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        elapsed = monotonic() - started

        if work_task in done:
            cancel_task.cancel()
            with suppress(asyncio.CancelledError):
                await cancel_task
            response = await work_task
            return self.complete_execution(
                execution_id,
                response,
                elapsed_seconds=elapsed,
            )

        work_task.cancel()
        with suppress(asyncio.CancelledError):
            await work_task

        if cancel_task in done:
            reason = (
                self.cancellations.reason(execution_id)
                or "execution cancelled"
            )
            self._finish_failure(
                execution_id,
                ExecutionStatus.CANCELLED,
                reason,
                elapsed,
            )
            raise KernelCancelledError(reason)

        cancel_task.cancel()
        with suppress(asyncio.CancelledError):
            await cancel_task
        reason = (
            f"execution exceeded {execution.budget.max_seconds} seconds"
        )
        self._finish_failure(
            execution_id,
            ExecutionStatus.TIMED_OUT,
            reason,
            elapsed,
        )
        raise KernelTimeoutError(reason)

    def complete_execution(
        self,
        execution_id: str,
        response: AggregatedResponse,
        *,
        elapsed_seconds: float,
    ) -> AggregatedResponse:
        execution = self.get_execution(execution_id)
        steps = self._artifact_integer(
            response.artifacts.get("node_count", 0)
        )
        usage = ResourceUsage(
            elapsed_seconds=elapsed_seconds,
            steps=steps,
        )
        if (
            execution.budget.max_steps is not None
            and steps > execution.budget.max_steps
        ):
            reason = (
                f"executed steps {steps} exceed budget "
                f"{execution.budget.max_steps}"
            )
            self._finish_failure(
                execution_id,
                ExecutionStatus.FAILED,
                reason,
                elapsed_seconds,
                usage=usage,
            )
            raise KernelBudgetError(reason)

        verification = self.verifier.verify(response)
        if response.status == "blocked":
            target_status = ExecutionStatus.BLOCKED
        elif verification.passed:
            target_status = ExecutionStatus.COMPLETED
        else:
            target_status = ExecutionStatus.FAILED
        self._update_execution(
            execution_id,
            {
                "status": target_status,
                "usage": usage,
                "verification": verification,
                "finished_at": datetime.now(UTC),
                "error": (
                    None if verification.passed else "verification failed"
                ),
            },
        )
        if target_status == ExecutionStatus.COMPLETED:
            self.goals.complete(execution.goal_id)
        elif target_status == ExecutionStatus.BLOCKED:
            self.goals.fail(execution.goal_id, "execution blocked")
        else:
            self.goals.fail(execution.goal_id, "verification failed")

        response.artifacts["kernel"] = {
            "execution_id": execution_id,
            "goal_id": execution.goal_id,
            "status": target_status.value,
            "budget": execution.budget.model_dump(mode="json"),
            "usage": usage.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
        }
        return response

    def mark_failed(self, execution_id: str, reason: str) -> None:
        execution = self.get_execution(execution_id)
        elapsed = 0.0
        if execution.started_at is not None:
            elapsed = (
                datetime.now(UTC) - execution.started_at
            ).total_seconds()
        self._finish_failure(
            execution_id,
            ExecutionStatus.FAILED,
            reason,
            elapsed,
        )

    def _finish_failure(
        self,
        execution_id: str,
        status: ExecutionStatus,
        reason: str,
        elapsed_seconds: float,
        *,
        usage: ResourceUsage | None = None,
    ) -> None:
        execution = self.get_execution(execution_id)
        final_usage = usage or ResourceUsage(
            elapsed_seconds=max(0.0, elapsed_seconds)
        )
        self._update_execution(
            execution_id,
            {
                "status": status,
                "usage": final_usage,
                "finished_at": datetime.now(UTC),
                "error": reason,
            },
        )
        if status == ExecutionStatus.CANCELLED:
            self.goals.cancel(execution.goal_id, reason)
        else:
            self.goals.fail(execution.goal_id, reason)

    @staticmethod
    def _artifact_integer(value: object) -> int:
        """Return an integer artifact value without unsafe coercion."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0

    def _update_execution(
        self,
        execution_id: str,
        updates: dict[str, Any],
    ) -> KernelExecution:
        execution = self.get_execution(execution_id)
        updated = execution.model_copy(update=updates)
        self._executions[execution_id] = updated
        if updated.status not in {
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
        }:
            self.cancellations.remove(execution_id)
        return updated
