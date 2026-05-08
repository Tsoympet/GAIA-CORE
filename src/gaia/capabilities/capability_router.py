"""Capability routing inspired by HuggingGPT model selection and OpenJarvis registries."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.agents.agent_registry import AgentRegistry
from gaia.capabilities.capability_registry import Capability, CapabilityRegistry


class RouteDecision(BaseModel):
    """Selected execution target for a planned task node."""

    requested_capabilities: list[str] = Field(default_factory=list)
    selected_agent: str
    selected_model: str = "local-bootstrap-reasoner"
    selected_tool: str = "none"
    execution_mode: str = "local_sync"
    candidate_agents: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    rationale: str

    @property
    def requested(self) -> list[str]:
        """Backward-compatible alias for older tests."""
        return self.requested_capabilities


class CapabilityRouter:
    """Route planned tasks to agents, models, tools, and execution modes."""

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
        """Choose the best currently registered target for requested capabilities."""
        requested = [capability.strip().lower() for capability in requested_capabilities or []]
        requested = [capability for capability in requested if capability] or ["reasoning"]
        candidates: dict[str, int] = {}
        approval = self._capabilities_require_approval(requested)
        for capability in requested:
            for agent in self.agent_registry.find_by_capability(capability):
                candidates[agent.name] = candidates.get(agent.name, 0) + 1
                approval = approval or agent.requires_human_approval
        if not candidates:
            fallback = self.agent_registry.get("gaia_core_agent")
            candidates[fallback.name] = 0
            rationale = "No exact capability match; fell back to the GAIA core agent."
        else:
            rationale = (
                "Selected the highest-overlap local agent plus local-first bootstrap "
                "model/tool hints for the requested capabilities."
            )
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

    def _select_model(self, capabilities: list[str]) -> str:
        if "coding" in capabilities or "repo" in capabilities:
            return "local-code-reasoner"
        if "vision" in capabilities:
            return "local-vision-adapter"
        if "audio" in capabilities or "voice" in capabilities or "speech" in capabilities:
            return "local-audio-voice-adapter"
        if "research" in capabilities:
            return "local-research-reasoner"
        return "local-bootstrap-reasoner"

    def _select_tool(self, capabilities: list[str]) -> str:
        if "coding" in capabilities or "repo" in capabilities:
            return "repository_inspector"
        if "memory" in capabilities:
            return "memory_search"
        if "security" in capabilities:
            return "policy_review"
        if "voice" in capabilities or "tts" in capabilities:
            return "voice_synthesizer"
        if "research" in capabilities:
            return "local_reference_summarizer"
        return "none"

    def _select_execution_mode(self, capabilities: list[str], approval: bool) -> str:
        if approval:
            return "requires_approval"
        if any(capability in capabilities for capability in ("coding", "tooling", "repo")):
            return "sandboxed_local_sync"
        return "local_sync"

    def _capabilities_require_approval(self, capabilities: list[str]) -> bool:
        risky = {"coding", "tooling", "repo", "self_evolve", "plugins"}
        for capability in capabilities:
            try:
                registered = self.capability_registry.get(capability)
            except KeyError:
                continue
            if registered.risky_actions:
                return True
        return bool(risky.intersection(capabilities))


def create_default_capability_router(agent_registry: AgentRegistry) -> CapabilityRouter:
    """Create the default capability router."""
    from gaia.capabilities.capability_registry import create_default_capability_registry

    return CapabilityRouter(create_default_capability_registry(), agent_registry)
