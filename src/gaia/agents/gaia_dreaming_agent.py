"""Dreaming agent for idle cognition and memory consolidation."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaDreamingAgent(BaseAgent):
    """Supports idle replay, memory consolidation, and goal rehearsal under permission gates."""

    metadata = AgentMetadata(
        name="gaia_dreaming_agent",
        description="Idle cognition, problem replay, memory consolidation, and goal rehearsal planning.",
        tags=("dreaming", "consolidation", "idle-cognition"),
    )
    capabilities = frozenset({"dreaming", "idle_cognition", "problem_replay", "goal_rehearsal", "memory_consolidation"})
    required_permissions = frozenset({Permission.READ_CONTEXT, Permission.READ_MEMORY, Permission.WRITE_MEMORY, Permission.DREAMING})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "dreaming"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "dreaming_focus": context.task,
                "cycle": ("select memories", "replay unresolved problems", "consolidate insights", "queue human-reviewable notes"),
                "requires_idle_window": True,
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
