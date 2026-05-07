"""Memory agent for recall, persistence, and consolidation requests."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaMemoryAgent(BaseAgent):
    """Handles memory recall and write planning under explicit memory permissions."""

    metadata = AgentMetadata(
        name="gaia_memory_agent",
        description="Memory recall, memory write planning, provenance, and consolidation support.",
        tags=("memory", "recall", "persistence"),
    )
    capabilities = frozenset({"memory", "recall", "memory_write", "consolidation", "provenance"})
    required_permissions = frozenset({Permission.READ_CONTEXT, Permission.READ_MEMORY, Permission.WRITE_MEMORY})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "memory"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "memory_task": context.task,
                "operations": ("recall relevant memories", "preserve provenance", "prepare consolidation candidates"),
                "workspace": context.metadata.get("workspace"),
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
