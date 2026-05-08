from pathlib import Path

import pytest

from gaia.core.runtime import TaskRequest, create_runtime
from gaia.orchestrator.planner import TaskPlanner


@pytest.mark.asyncio
async def test_planner_produces_dependency_ordered_structured_steps() -> None:
    plan = await TaskPlanner().create_plan(
        "Research and code a local-first routing improvement",
        ["research", "coding"],
    )

    assert [step.id for step in plan.steps] == ["step-1", "step-2"]
    assert plan.steps[1].dependencies == ["step-1"]
    assert [node.id for node in plan.graph.execution_order()] == ["step-1", "step-2"]


@pytest.mark.asyncio
async def test_orchestrator_plan_includes_route_metadata_for_each_step() -> None:
    runtime = create_runtime(config_dir=Path("config"))

    plan = await runtime.orchestrator.plan(
        "Research and code a local-first routing improvement",
        ["research", "coding"],
    )

    assert len(plan.steps) == 2
    assert [route.selected_agent for route in plan.routes] == [
        "gaia_research_agent",
        "gaia_code_agent",
    ]
    assert plan.routes[1].selected_model == "local-code-reasoner"
    assert plan.routes[1].selected_tool == "permission_checked_repo_tools"
    assert plan.graph.nodes[1].execution_mode == "permission_gated"


@pytest.mark.asyncio
async def test_runtime_runs_phase_three_pipeline_with_reflection() -> None:
    runtime = create_runtime(config_dir=Path("config"))

    response = await runtime.submit_task(
        TaskRequest(
            task="Research and code a local-first routing improvement",
            capabilities=["research", "coding"],
        )
    )

    assert response.status == "completed"
    assert response.agents == ["gaia_research_agent", "gaia_code_agent"]
    assert response.reflection is not None
    assert response.artifacts["pipeline"][-1] == "reflection_loop"
    assert response.artifacts["node_count"] == 2
async def test_planner_creates_structured_multistep_plan_for_inferred_tasks() -> None:
    plan = await TaskPlanner().create_plan("Research local-first model routing")

    assert [step.id for step in plan.steps] == ["step-1", "step-2", "step-3"]
    assert plan.graph.nodes[1].dependencies == ["step-1"]
    assert plan.graph.nodes[2].required_capabilities == ["reflection"]


@pytest.mark.asyncio
async def test_runtime_pipeline_records_routes_and_reflection() -> None:
    runtime = create_runtime(Path("config"))

    response = await runtime.submit_task(TaskRequest(task="Research local-first model routing"))

    routes = response.artifacts["routes"]
    assert response.status == "completed"
    assert response.artifacts["node_count"] == 3
    assert routes[1]["selected_model"] == "local-reasoning-model"
    assert routes[1]["selected_tool"] == "research_summarizer"
    assert response.artifacts["reflection"]["confidence"]["uncertainty"] >= 0
    assert runtime.memory_store.events[-1].event_type == "reflection_completed"
