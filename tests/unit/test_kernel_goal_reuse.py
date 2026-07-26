import pytest

from gaia.kernel import CognitiveKernel, GoalStatus


def test_kernel_reuses_active_goal_for_execution() -> None:
    kernel = CognitiveKernel()
    goal = kernel.goals.create("Continue Cognitive Kernel implementation")
    kernel.goals.activate(goal.goal_id)

    execution = kernel.begin_execution(
        objective="Continue Cognitive Kernel implementation",
        session_id="session-1",
        capabilities=["reasoning"],
        goal_id=goal.goal_id,
    )

    assert execution.goal_id == goal.goal_id
    assert kernel.goals.get(goal.goal_id).status == GoalStatus.ACTIVE


def test_kernel_rejects_terminal_goal_reuse() -> None:
    kernel = CognitiveKernel()
    goal = kernel.goals.create("Completed goal")
    kernel.goals.activate(goal.goal_id)
    kernel.goals.complete(goal.goal_id)

    with pytest.raises(ValueError, match="not executable"):
        kernel.begin_execution(
            objective="Try terminal goal",
            session_id="session-1",
            capabilities=["reasoning"],
            goal_id=goal.goal_id,
        )
