"""Capability routing primitives."""

from pydantic import BaseModel, Field

from gaia.agents.registry import AgentRegistry


class Capability(BaseModel):
    """A routable capability domain."""

    name: str
    description: str
    local_first: bool = True


class RouteDecision(BaseModel):
    """Decision describing which agents can handle requested capabilities."""

    requested: list[str]
    candidate_agents: list[str]
    requires_human_approval: bool = False


class CapabilityRouter(BaseModel):
    """Routes objectives to specialized agents by capability."""

    agent_registry: AgentRegistry
    capabilities: dict[str, Capability] = Field(default_factory=dict)

    def list_capabilities(self) -> list[Capability]:
        """Return stable sorted capability descriptors."""
        return [self.capabilities[name] for name in sorted(self.capabilities)]

    def route(self, requested: list[str]) -> RouteDecision:
        """Route capability names to candidate agents."""
        candidate_names: set[str] = set()
        requires_approval = False
        for capability in requested or ["reasoning"]:
            for agent in self.agent_registry.find_by_capability(capability):
                candidate_names.add(agent.name)
                requires_approval = requires_approval or agent.requires_human_approval
        return RouteDecision(
            requested=requested or ["reasoning"],
            candidate_agents=sorted(candidate_names),
            requires_human_approval=requires_approval,
        )


def create_default_capability_router(agent_registry: AgentRegistry) -> CapabilityRouter:
    """Create the default local-first capability router."""
    capability_names = {
        "reasoning": "General reasoning and synthesis.",
        "planning": "Task decomposition and execution planning.",
        "research": "Research and evidence gathering.",
        "coding": "Software engineering and repository operations.",
        "tooling": "Audited tool execution.",
        "engineering": "Engineering analysis workflows.",
        "vision": "Visual and multimodal analysis.",
        "audio": "Audio processing and transcription.",
        "memory": "Persistent memory recall and consolidation.",
        "security": "Policy enforcement and audit review.",
        "self_model": "Introspection and capability mapping.",
        "dreaming": "Idle cognition and memory replay.",
        "self_evolve": "Human-approved platform improvement proposals.",
    }
    return CapabilityRouter(
        agent_registry=agent_registry,
        capabilities={
            name: Capability(name=name, description=description)
            for name, description in capability_names.items()
        },
    )
