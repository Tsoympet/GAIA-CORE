from pathlib import Path

import pytest

from gaia.core.runtime import TaskRequest, create_runtime
from gaia.orchestrator.planner import TaskPlanner


@pytest.mark.asyncio
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
