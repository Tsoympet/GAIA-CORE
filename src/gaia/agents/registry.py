"""Agent descriptors and discovery registry."""

from pydantic import BaseModel, Field


class AgentDescriptor(BaseModel):
    """Metadata for a specialized GAIA agent."""

    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False


class AgentRegistry(BaseModel):
    """In-memory registry for specialized autonomous agents."""

    agents: dict[str, AgentDescriptor] = Field(default_factory=dict)

    def register(self, descriptor: AgentDescriptor) -> None:
        """Register or replace an agent descriptor."""
        self.agents[descriptor.name] = descriptor

    def list_agent_names(self) -> list[str]:
        """Return stable sorted agent names."""
        return sorted(self.agents)

    def find_by_capability(self, capability: str) -> list[AgentDescriptor]:
        """Find agents that advertise a capability."""
        return [agent for agent in self.agents.values() if capability in agent.capabilities]


def create_default_agent_registry() -> AgentRegistry:
    """Create the initial multi-agent registry from the README architecture."""
    registry = AgentRegistry()
    for descriptor in [
        AgentDescriptor(
            name="gaia_core_agent",
            description="General runtime coordination.",
            capabilities=["reasoning", "planning"],
        ),
        AgentDescriptor(
            name="gaia_research_agent",
            description="Research collection and synthesis.",
            capabilities=["research"],
        ),
        AgentDescriptor(
            name="gaia_code_agent",
            description="Software engineering task execution.",
            capabilities=["coding", "tooling"],
        ),
        AgentDescriptor(
            name="gaia_engineer_agent",
            description="Engineering analysis and CAD-oriented workflows.",
            capabilities=["engineering"],
        ),
        AgentDescriptor(
            name="gaia_vision_agent",
            description="Image and multimodal visual understanding.",
            capabilities=["vision"],
        ),
        AgentDescriptor(
            name="gaia_audio_agent",
            description="Audio transcription and analysis.",
            capabilities=["audio"],
        ),
        AgentDescriptor(
            name="gaia_memory_agent",
            description="Memory consolidation and recall.",
            capabilities=["memory"],
        ),
        AgentDescriptor(
            name="gaia_security_agent",
            description="Policy review, audit, and sandbox governance.",
            capabilities=["security"],
        ),
        AgentDescriptor(
            name="gaia_self_model_agent",
            description="Capability mapping and introspective review.",
            capabilities=["self_model"],
        ),
        AgentDescriptor(
            name="gaia_dreaming_agent",
            description="Idle cognition and memory replay.",
            capabilities=["dreaming"],
        ),
        AgentDescriptor(
            name="gaia_self_evolve_agent",
            description="Human-approved platform improvement proposals.",
            capabilities=["self_evolve"],
            requires_human_approval=True,
        ),
    ]:
        registry.register(descriptor)
    return registry
