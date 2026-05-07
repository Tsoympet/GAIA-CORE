from gaia.agents.agent_registry import create_default_agent_registry


def test_agent_registry_lists_and_describes_agents() -> None:
    registry = create_default_agent_registry()

    descriptor = registry.describe("gaia_core_agent")

    assert descriptor.name == "gaia_core_agent"
    assert "reasoning" in descriptor.capabilities


def test_default_registry_contains_required_gaia_agents() -> None:
    registry = create_default_agent_registry()

    required = {
        "gaia_core_agent",
        "gaia_research_agent",
        "gaia_code_agent",
        "gaia_engineer_agent",
        "gaia_vision_agent",
        "gaia_audio_agent",
        "gaia_memory_agent",
        "gaia_security_agent",
        "gaia_documents_agent",
        "gaia_repo_agent",
        "gaia_cad_agent",
        "gaia_self_model_agent",
        "gaia_reflection_agent",
        "gaia_metacognition_agent",
        "gaia_dreaming_agent",
        "gaia_idle_reflection_agent",
    }

    assert required.issubset(set(registry.list_agent_names()))
