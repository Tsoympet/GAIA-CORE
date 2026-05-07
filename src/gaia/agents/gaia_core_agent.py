"""Core coordination agent for GAIA task intake and planning."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaCoreAgent(BaseAgent):
    """Coordinates general task intake, planning, and agent handoff recommendations."""

    metadata = AgentMetadata(
        name="gaia_core_agent",
        description="General task intake, high-level planning, and orchestration guidance.",
        tags=("core", "planning", "orchestration"),
    )
    capabilities = frozenset({"core", "planning", "orchestration", "task_intake", "routing"})
    required_permissions = frozenset({Permission.READ_CONTEXT})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "planning"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "summary": f"Prepared orchestration plan for task: {context.task}",
                "recommended_next_capabilities": tuple(sorted(self.capabilities - {"core"})),
                "inputs_received": tuple(sorted(context.inputs.keys())),
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
