import asyncio

import pytest

from gaia.core import TaskRequest, create_runtime
from gaia.kernel import (
    CognitiveKernel,
    ExecutionStatus,
    GoalStatus,
    KernelBudgetError,
    KernelCancelledError,
    KernelTimeoutError,
    ResourceBudget,
)
from gaia.orchestrator.aggregator import AggregatedResponse


def test_goal_manager_enforces_lifecycle_transitions() -> None:
    kernel = CognitiveKernel()
    goal = kernel.goals.create("Build the Cognitive Kernel", priority=90)

    active = kernel.goals.activate(goal.goal_id)
    completed = kernel.goals.complete(goal.goal_id)

    assert active.status == GoalStatus.ACTIVE
    assert completed.status == GoalStatus.COMPLETED
    with pytest.raises(ValueError, match="cannot transition"):
        kernel.goals.activate(goal.goal_id)


def test_kernel_rejects_plan_that_exceeds_step_budget() -> None:
    kernel = CognitiveKernel()

    with pytest.raises(KernelBudgetError, match="planned steps"):
        kernel.begin_execution(
            objective="Research and verify a design",
            session_id="session-1",
            capabilities=["research", "security"],
            budget=ResourceBudget(max_steps=1),
        )


@pytest.mark.asyncio
async def test_kernel_enforces_wall_clock_timeout() -> None:
    kernel = CognitiveKernel()
    execution = kernel.begin_execution(
        objective="Slow test operation",
        session_id="session-1",
        capabilities=["reasoning"],
        budget=ResourceBudget(max_seconds=0.01),
    )

    async def operation() -> AggregatedResponse:
        await asyncio.sleep(0.1)
        return AggregatedResponse(
            task_id="slow-task",
            status="completed",
            answer="finished",
            confidence=1.0,
            artifacts={"node_count": 1},
        )

    with pytest.raises(KernelTimeoutError, match="exceeded"):
        await kernel.run_guarded(execution.execution_id, operation)

    stored = kernel.get_execution(execution.execution_id)
    assert stored.status == ExecutionStatus.TIMED_OUT
    assert kernel.goals.get(execution.goal_id).status == GoalStatus.FAILED


@pytest.mark.asyncio
async def test_kernel_supports_cooperative_cancellation() -> None:
    kernel = CognitiveKernel()
    execution = kernel.begin_execution(
        objective="Cancellable operation",
        session_id="session-1",
        capabilities=["reasoning"],
    )

    async def operation() -> AggregatedResponse:
        await asyncio.sleep(1)
        return AggregatedResponse(
            task_id="cancel-task",
            status="completed",
            answer="finished",
            confidence=1.0,
            artifacts={"node_count": 1},
        )

    task = asyncio.create_task(
        kernel.run_guarded(execution.execution_id, operation)
    )
    await asyncio.sleep(0)
    kernel.request_cancellation(
        execution.execution_id,
        "operator requested cancellation",
    )

    with pytest.raises(KernelCancelledError, match="operator requested"):
        await task

    stored = kernel.get_execution(execution.execution_id)
    assert stored.status == ExecutionStatus.CANCELLED
    assert kernel.goals.get(execution.goal_id).status == GoalStatus.CANCELLED


@pytest.mark.asyncio
async def test_runtime_executes_through_kernel_and_records_verification() -> None:
    runtime = create_runtime()

    response = await runtime.submit_task(
        TaskRequest(
            task="Research local-first model routing",
            capabilities=["research"],
            budget=ResourceBudget(max_steps=2, max_seconds=5),
        )
    )

    kernel_artifact = response.artifacts["kernel"]
    execution = runtime.kernel.get_execution(
        kernel_artifact["execution_id"]
    )

    assert response.status == "completed"
    assert kernel_artifact["status"] == "completed"
    assert kernel_artifact["verification"]["passed"] is True
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.usage.steps == 1
    assert runtime.kernel.status().active_executions == 0
