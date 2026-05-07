"""Agent registry and default bootstrap agents for GAIA."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.agents.base_agent import BaseAgent, CapabilityAgent, LocalReasoningAgent


class AgentDescriptor(BaseModel):
    """Metadata advertised by a registered GAIA agent."""

    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False


class AgentRegistry:
    """In-memory registry for local-first specialized agents."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register or replace an agent instance."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent:
        """Return an agent by name or raise a clear KeyError."""
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"agent is not registered: {name}") from exc

    def list_agent_names(self) -> list[str]:
        """Return registered agent names in stable order."""
        return sorted(self._agents)

    def list_descriptors(self) -> list[AgentDescriptor]:
        """Return public descriptors for all agents."""
        return [self.describe(name) for name in self.list_agent_names()]

    def describe(self, name: str) -> AgentDescriptor:
        """Return metadata for one agent."""
        agent = self.get(name)
        return AgentDescriptor(
            name=agent.name,
            description=agent.description,
            capabilities=list(agent.capabilities),
            requires_human_approval=agent.requires_human_approval,
        )

    def find_by_capability(self, capability: str) -> list[BaseAgent]:
        """Find agents that advertise a capability."""
        return [agent for agent in self._agents.values() if capability in agent.capabilities]


def create_default_agent_registry() -> AgentRegistry:
    """Create GAIA's initial specialized-agent registry."""
    registry = AgentRegistry()
    registry.register(LocalReasoningAgent())
    for name, description, capabilities in [
        ("gaia_research_agent", "Research collection and synthesis.", ("research",)),
        (
            "gaia_code_agent",
            "Software engineering assistance under permission gates.",
            ("coding", "tooling"),
        ),
        ("gaia_engineer_agent", "Engineering analysis and design workflows.", ("engineering",)),
        ("gaia_memory_agent", "Memory recall and consolidation.", ("memory",)),
        ("gaia_security_agent", "Policy review, audit, and sandbox governance.", ("security",)),
        ("gaia_self_model_agent", "Simulated self-model and capability review.", ("self_model",)),
        ("gaia_metacognition_agent", "Confidence and reflective review.", ("metacognition",)),
        ("gaia_dreaming_agent", "Safe idle cognition and replay simulation.", ("dreaming",)),
        (
            "gaia_self_evolve_agent",
            "Human-approved platform improvement proposals.",
            ("self_evolve",),
        ),
    ]:
        registry.register(CapabilityAgent(name, description, capabilities))
    return registry
