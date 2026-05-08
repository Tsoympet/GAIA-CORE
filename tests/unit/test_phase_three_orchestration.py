from pathlib import Path

import pytest

from gaia.core.runtime import TaskRequest, create_runtime
from gaia.orchestrator.planner import TaskPlanner


@pytest.mark.asyncio
async def test_phase_three_planner_builds_multi_step_graph() -> None:
    plan = await TaskPlanner().create_plan(
        "Research and secure a repository workflow",
        ["research", "security"],
    )

    assert [step.id for step in plan.steps] == ["step-1", "step-2", "step-3"]
    assert plan.graph.nodes[1].dependencies == ["step-1"]
    assert plan.graph.nodes[2].required_capabilities == ["reasoning"]
    assert [node.id for node in plan.graph.execution_order()] == ["step-1", "step-2", "step-3"]


@pytest.mark.asyncio
async def test_phase_three_runtime_returns_routes_and_reflection() -> None:
    runtime = create_runtime(Path("config"))

    response = await runtime.submit_task(
        TaskRequest(
            task="Research and secure a repository workflow",
            capabilities=["research", "security"],
        )
    )

    assert response.status == "completed"
    assert response.artifacts["node_count"] == 3
    assert response.artifacts["pipeline"][-2:] == ["reflection_pass", "final_response"]
    assert "reflection" in response.artifacts
    routes = response.artifacts["routes"]
    assert routes[0]["selected_model"] == "local-research-reasoner"
    assert routes[1]["selected_tool"] == "policy_review"
