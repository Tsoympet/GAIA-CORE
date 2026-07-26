"""Capability routing for GAIA agents, model profiles, and safe tool adapters."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.agents.agent_registry import AgentRegistry
from gaia.capabilities.capability_registry import Capability, CapabilityRegistry


class RouteDecision(BaseModel):
    """Selected execution target for a planned task node."""

    requested_capabilities: list[str] = Field(default_factory=list)
    selected_agent: str
    selected_model: str
    selected_tool: str
    execution_mode: str = "local"
    candidate_agents: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    rationale: str

    @property
    def requested(self) -> list[str]:
        """Backward-compatible alias for earlier callers."""
        return self.requested_capabilities


class CapabilityRouter:
    """Route tasks to the highest-overlap registered local agent."""

    _RISKY_CAPABILITIES = {
        "coding",
        "tooling",
        "repo",
        "plugins",
        "self_evolve",
    }

    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        agent_registry: AgentRegistry,
    ) -> None:
        self.capability_registry = capability_registry
        self.agent_registry = agent_registry

    def list_capabilities(self) -> list[Capability]:
        """Return known capabilities."""
        return self.capability_registry.list_capabilities()

    def route(
        self,
        requested_capabilities: list[str] | tuple[str, ...] | None = None,
    ) -> RouteDecision:
        """Choose one agent and local-first execution profile."""
        requested = self._normalize(requested_capabilities)
        candidates: dict[str, int] = {}
        requires_approval = self._capabilities_require_approval(requested)

        for capability in requested:
            for agent in self.agent_registry.find_by_capability(capability):
                candidates[agent.name] = candidates.get(agent.name, 0) + 1
                requires_approval = (
                    requires_approval or agent.requires_human_approval
                )

        if candidates:
            selected_agent = sorted(
                candidates.items(),
                key=lambda item: (-item[1], item[0]),
            )[0][0]
            rationale = (
                "Selected the highest-overlap registered local agent and "
                "a capability-specific local model/tool profile."
            )
        else:
            selected_agent = self.agent_registry.get("gaia_core_agent").name
            candidates[selected_agent] = 0
            rationale = (
                "No exact capability match was available; "
                "fell back to the GAIA core agent."
            )

        return RouteDecision(
            requested_capabilities=requested,
            selected_agent=selected_agent,
            selected_model=self._select_model(requested),
            selected_tool=self._select_tool(requested),
            execution_mode=self._select_execution_mode(
                requested,
                requires_approval,
            ),
            candidate_agents=sorted(candidates),
            requires_human_approval=requires_approval,
            rationale=rationale,
        )

    def _normalize(
        self,
        requested_capabilities: list[str] | tuple[str, ...] | None,
    ) -> list[str]:
        normalized: list[str] = []
        for capability in requested_capabilities or ("reasoning",):
            value = capability.strip().lower()
            if value and value not in normalized:
                normalized.append(value)
        return normalized or ["reasoning"]

    def _select_model(self, capabilities: list[str]) -> str:
        if any(
            capability in capabilities
            for capability in ("coding", "repo")
        ):
            return "local-code-reasoner"
        if any(
            capability in capabilities
            for capability in ("vision", "documents", "cad")
        ):
            return "local-multimodal-reasoner"
        if any(
            capability in capabilities
            for capability in ("audio", "speech", "stt", "tts", "voice")
        ):
            return "local-audio-voice-stack"
        return "local-general-reasoner"

    def _select_tool(self, capabilities: list[str]) -> str:
        if any(
            capability in capabilities
            for capability in ("coding", "repo", "tooling")
        ):
            return "permission_checked_repo_tools"
        if "research" in capabilities:
            return "local_research_scratchpad"
        if "memory" in capabilities:
            return "memory_manager"
        if "security" in capabilities:
            return "policy_review"
        if any(
            capability in capabilities
            for capability in ("voice", "speech", "tts", "stt")
        ):
            return "voice_router"
        return "no_external_tool"

    def _select_execution_mode(
        self,
        capabilities: list[str],
        requires_approval: bool,
    ) -> str:
        if (
            requires_approval
            or self._RISKY_CAPABILITIES.intersection(capabilities)
        ):
            return "permission_gated"
        if any(
            capability in capabilities
            for capability in ("voice", "audio", "speech")
        ):
            return "local_with_text_fallback"
        return "local"

    def _capabilities_require_approval(
        self,
        capabilities: list[str],
    ) -> bool:
        if self._RISKY_CAPABILITIES.intersection(capabilities):
            return True

        for capability in capabilities:
            try:
                registered = self.capability_registry.get(capability)
            except KeyError:
                continue
            if registered.risky_actions:
                return True

        return False


def create_default_capability_router(
    agent_registry: AgentRegistry,
) -> CapabilityRouter:
    """Create the default capability router."""
    from gaia.capabilities.capability_registry import (
        create_default_capability_registry,
    )

    return CapabilityRouter(
        create_default_capability_registry(),
        agent_registry,
    )
