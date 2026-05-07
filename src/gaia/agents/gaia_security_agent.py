"""Security agent for permission, policy, and audit review."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaSecurityAgent(BaseAgent):
    """Reviews requested actions against GAIA permission and audit expectations."""

    metadata = AgentMetadata(
        name="gaia_security_agent",
        description="Security policy review, permission analysis, risk scoring, and audit guidance.",
        tags=("security", "policy", "audit"),
    )
    capabilities = frozenset({"security", "permission_review", "policy_review", "risk_scoring", "audit"})
    required_permissions = frozenset({Permission.READ_CONTEXT, Permission.SECURITY_REVIEW})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "security"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "review_target": context.task,
                "checks": ("permission sufficiency", "sandbox boundary", "audit logging", "human approval gates"),
                "default_posture": "deny unless explicitly granted",
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
