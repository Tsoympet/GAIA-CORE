from pathlib import Path

import pytest

from gaia.core import create_runtime


@pytest.mark.asyncio
async def test_orchestrator_creates_auditable_task_graph() -> None:
    runtime = create_runtime(config_dir=Path("config"))

    plan = await runtime.orchestrator.plan("Research local-first model routing", ["research"])

    assert plan.security.allowed is True
    assert plan.graph.objective == "Research local-first model routing"
    assert plan.graph.nodes[0].required_capabilities == ["research"]
    assert plan.routes[0].candidate_agents == ["gaia_research_agent"]
    assert runtime.memory_store.events[0].event_type == "plan_created"
