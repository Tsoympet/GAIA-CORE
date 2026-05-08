"""Capability routing inspired by HuggingGPT model selection and OpenJarvis registries."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.agents.agent_registry import AgentRegistry
from gaia.capabilities.capability_registry import Capability, CapabilityRegistry


class RouteDecision(BaseModel):
    """Selected execution target for a planned task node."""

    requested_capabilities: list[str] = Field(default_factory=list)
    selected_agent: str
    selected_model: str
    selected_tool: str | None = None
    execution_mode: str = "local"
    candidate_agents: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    rationale: str

    @property
    def requested(self) -> list[str]:
        """Backward-compatible alias for older tests."""
        return self.requested_capabilities


class CapabilityRouter:
    """Route planned tasks to agents based on advertised capabilities."""

    def __init__(
        self, capability_registry: CapabilityRegistry, agent_registry: AgentRegistry
    ) -> None:
        self.capability_registry = capability_registry
        self.agent_registry = agent_registry

    def list_capabilities(self) -> list[Capability]:
        """Return known capabilities."""
        return self.capability_registry.list()

    def route(
        self, requested_capabilities: list[str] | tuple[str, ...] | None = None
    ) -> RouteDecision:
        """Choose the best currently registered agent for requested capabilities."""
        requested = list(requested_capabilities or ["reasoning"])
        candidates: dict[str, int] = {}
        approval = False
        for capability in requested:
            for agent in self.agent_registry.find_by_capability(capability):
                candidates[agent.name] = candidates.get(agent.name, 0) + 1
                approval = approval or agent.requires_human_approval
        if not candidates:
            fallback = self.agent_registry.get("gaia_core_agent")
            candidates[fallback.name] = 0
            rationale = "No exact capability match; fell back to the GAIA core agent."
        else:
            rationale = "Selected the highest-overlap local agent for the requested capabilities."
        selected = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[0][0]
        return RouteDecision(
            requested_capabilities=requested,
            selected_agent=selected,
            selected_model=self._select_model(requested),
            selected_tool=self._select_tool(requested),
            execution_mode=self._select_execution_mode(requested, approval),
            candidate_agents=sorted(candidates),
            requires_human_approval=approval,
            rationale=rationale,
        )

    def _select_model(self, requested: list[str]) -> str:
        """Select a local-first model family for the capability request."""
        if any(capability in requested for capability in ("coding", "repo")):
            return "local-code-model"
        if any(capability in requested for capability in ("vision", "audio", "voice")):
            return "local-multimodal-model"
        return "local-reasoning-model"

    def _select_tool(self, requested: list[str]) -> str | None:
        """Select a safe internal tool adapter without performing external actions."""
        if "memory" in requested:
            return "memory_search"
        if "coding" in requested or "repo" in requested:
            return "repo_inspector"
        if "research" in requested:
            return "research_summarizer"
        return None

    def _select_execution_mode(self, requested: list[str], approval: bool) -> str:
        """Select execution mode while preserving human approval gates."""
        if approval:
            return "human_approval_required"
        if any(capability in requested for capability in ("coding", "tooling", "repo")):
            return "sandboxed"
        return "local"


def create_default_capability_router(agent_registry: AgentRegistry) -> CapabilityRouter:
    """Create the default capability router."""
    from gaia.capabilities.capability_registry import create_default_capability_registry

    return CapabilityRouter(create_default_capability_registry(), agent_registry)
