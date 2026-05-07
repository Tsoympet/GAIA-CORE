"""Self-model agent for capability and limitation introspection."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaSelfModelAgent(BaseAgent):
    """Maintains capability maps, limitations, uncertainty, and self-assessment outputs."""

    metadata = AgentMetadata(
        name="gaia_self_model_agent",
        description="Capability mapping, limitation tracking, confidence estimation, and self-assessment.",
        tags=("self-model", "introspection", "confidence"),
    )
    capabilities = frozenset({"self_model", "capability_mapping", "limitation_tracking", "confidence_estimation"})
    required_permissions = frozenset({Permission.READ_CONTEXT, Permission.SELF_MODEL_READ, Permission.SYSTEM_INTROSPECTION})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "self_model"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "self_model_task": context.task,
                "assessment_fields": ("known capabilities", "known limits", "uncertainty", "confidence"),
                "human_governance_required": False,
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
