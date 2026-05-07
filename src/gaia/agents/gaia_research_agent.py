"""Research agent for source discovery and evidence synthesis."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaResearchAgent(BaseAgent):
    """Plans and summarizes research workflows without bypassing network permissions."""

    metadata = AgentMetadata(
        name="gaia_research_agent",
        description="Research planning, source discovery strategy, and evidence synthesis.",
        tags=("research", "analysis", "sources"),
    )
    capabilities = frozenset({"research", "source_discovery", "evidence_synthesis", "fact_checking"})
    required_permissions = frozenset({Permission.READ_CONTEXT, Permission.NETWORK_ACCESS})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "research"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "research_question": context.task,
                "strategy": ("identify primary sources", "cross-check claims", "summarize with citations"),
                "network_access_granted": Permission.NETWORK_ACCESS in context.granted_permissions,
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
