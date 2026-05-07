import pytest

from gaia.agents.agent_registry import create_default_agent_registry
from gaia.capabilities.capability_router import create_default_capability_router
from gaia.orchestrator.aggregator import ResultAggregator
from gaia.orchestrator.executor import MultiAgentExecutor
from gaia.orchestrator.planner import TaskPlanner


@pytest.mark.asyncio
async def test_planner_executor_and_aggregator_pipeline() -> None:
    agents = create_default_agent_registry()
    router = create_default_capability_router(agents)
    plan = await TaskPlanner().create_plan("Research local-first routing", ["research"])

    report = await MultiAgentExecutor(agents, router).execute(plan.graph, "session-1")
    response = await ResultAggregator().aggregate(plan.objective, report)

    assert response.status == "completed"
    assert response.agents == ["gaia_research_agent"]
    assert response.artifacts["node_count"] == 1
