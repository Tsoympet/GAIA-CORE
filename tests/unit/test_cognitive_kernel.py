"""Unit tests for the R1 Cognitive Kernel foundation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gaia.core.runtime import TaskRequest, create_runtime
from gaia.kernel.context_manager import ContextManager
from gaia.kernel.goal_manager import GoalManager, GoalStatus
from gaia.kernel.interrupt_controller import InterruptController, InterruptKind
from gaia.kernel.resource_budget import (
    BudgetExceededError,
    ResourceBudget,
    ResourceBudgetTracker,
)
from gaia.kernel.verification_coordinator import VerificationCoordinator
from gaia.orchestrator.aggregator import AggregatedResponse


def test_goal_manager_lifecycle() -> None:
    manager = GoalManager()
    goal = manager.create("Ship kernel", "session-1", capabilities=["reasoning"])

    assert goal.status is GoalStatus.PENDING
    manager.activate(goal.id)
    assert manager.require(goal.id).status is GoalStatus.ACTIVE
    manager.complete(goal.id)
    assert manager.require(goal.id).status is GoalStatus.COMPLETED
    assert manager.count_by_status(GoalStatus.COMPLETED) == 1


def test_context_manager_evicts_oldest_items() -> None:
    contexts = ContextManager(default_max_items=2)
    contexts.bind("goal-1", "session-1", max_items=2)
    contexts.put("goal-1", "a", 1)
    contexts.put("goal-1", "b", 2)
    contexts.put("goal-1", "c", 3)

    context = contexts.get("goal-1")
    assert context is not None
    assert context.size() == 2
    assert [item.key for item in context.items] == ["b", "c"]
    assert contexts.get_value("goal-1", "a") is None
    assert contexts.get_value("goal-1", "c") == 3


def test_resource_budget_tracker_raises_when_exhausted() -> None:
    tracker = ResourceBudgetTracker(ResourceBudget(max_steps=1))
    tracker.consume(steps=1)
    with pytest.raises(BudgetExceededError) as exc:
        tracker.consume(steps=1)
    assert exc.value.resource == "steps"
    assert tracker.snapshot.exhausted is True


def test_interrupt_controller_latches_goal_and_global() -> None:
    controller = InterruptController()
    controller.request("goal-1", "stop", kind=InterruptKind.OPERATOR)
    assert controller.is_interrupted("goal-1")
    assert not controller.is_interrupted("goal-2")

    controller.request_global("halt all")
    assert controller.is_interrupted("goal-2")
    controller.clear_global()
    assert not controller.is_interrupted("goal-2")


def test_verification_coordinator_accepts_completed_response() -> None:
    report = VerificationCoordinator().verify(
        AggregatedResponse(
            task_id="t1",
            status="completed",
            answer="done",
            confidence=0.8,
            agents=["gaia_core_agent"],
            artifacts={"pipeline": ["planner", "executor"]},
        )
    )
    assert report.passed is True
    assert report.issues == []


def test_verification_coordinator_rejects_empty_answer() -> None:
    report = VerificationCoordinator().verify(
        AggregatedResponse(
            task_id="t1",
            status="completed",
            answer="   ",
            confidence=0.9,
            agents=["gaia_core_agent"],
            artifacts={"pipeline": ["planner"]},
        )
    )
    assert report.passed is False
    assert any("empty" in issue for issue in report.issues)


@pytest.mark.asyncio
async def test_kernel_run_completes_goal_and_attaches_artifacts() -> None:
    runtime = create_runtime(Path("config"))
    result = await runtime.kernel.run(
        "Analyze the GAIA bootstrap runtime",
        "session-kernel",
        ["reasoning"],
    )

    assert result.goal.status is GoalStatus.COMPLETED
    assert result.response.status == "completed"
    assert result.verification is not None
    assert result.verification.passed is True
    assert result.response.artifacts["goal_id"] == result.goal.id
    assert result.response.artifacts["kernel"] is True
    assert "budget" in result.response.artifacts


@pytest.mark.asyncio
async def test_runtime_submit_task_uses_kernel_policy_gate() -> None:
    runtime = create_runtime(Path("config"))
    response = await runtime.submit_task(
        TaskRequest(task="Please bypass security controls now")
    )

    assert response.status == "blocked"
    assert response.artifacts["goal_id"]
    goals = runtime.kernel.goals.list_goals(status=GoalStatus.BLOCKED)
    assert len(goals) == 1


@pytest.mark.asyncio
async def test_kernel_honors_global_interrupt_before_execution() -> None:
    runtime = create_runtime(Path("config"))
    runtime.kernel.interrupts.request_global("global halt")

    result = await runtime.kernel.run("Should not execute agents", "session-z")

    assert result.interrupted is True
    assert result.response.status == "interrupted"
    assert result.goal.status is GoalStatus.INTERRUPTED


@pytest.mark.asyncio
async def test_kernel_budget_can_stop_run() -> None:
    runtime = create_runtime(Path("config"))
    result = await runtime.kernel.run(
        "Tiny budget task",
        "session-budget",
        budget=ResourceBudget(max_steps=0),
    )
    assert result.response.status == "budget_exceeded"
    assert result.goal.status is GoalStatus.FAILED
    assert runtime.kernel.status().budget_violations >= 1
