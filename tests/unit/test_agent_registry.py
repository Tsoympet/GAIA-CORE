from gaia.agents.agent_registry import create_default_agent_registry


def test_agent_registry_lists_and_describes_agents() -> None:
    registry = create_default_agent_registry()

    descriptor = registry.describe("gaia_core_agent")

    assert descriptor.name == "gaia_core_agent"
    assert "reasoning" in descriptor.capabilities
