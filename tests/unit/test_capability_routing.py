from gaia.agents.agent_registry import create_default_agent_registry
from gaia.capabilities.capability_router import create_default_capability_router


def test_capability_router_selects_matching_agent() -> None:
    agents = create_default_agent_registry()
    router = create_default_capability_router(agents)

    decision = router.route(["research"])

    assert decision.selected_agent == "gaia_research_agent"
    assert "gaia_research_agent" in decision.candidate_agents
