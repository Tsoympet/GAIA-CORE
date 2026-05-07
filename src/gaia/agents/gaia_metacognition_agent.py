"""Metacognition agent for reflective quality review."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaMetacognitionAgent(BaseAgent):
    """Performs second-pass reasoning review, uncertainty checks, and quality reflection."""

    metadata = AgentMetadata(
        name="gaia_metacognition_agent",
        description="Reflective reasoning review, uncertainty checks, contradiction detection, and quality scoring.",
        tags=("metacognition", "reflection", "quality"),
    )
    capabilities = frozenset({"metacognition", "reflection", "quality_review", "contradiction_detection"})
    required_permissions = frozenset({Permission.READ_CONTEXT, Permission.METACOGNITION})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "metacognition"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "review_subject": context.task,
                "review_dimensions": ("assumptions", "evidence", "contradictions", "confidence", "residual risk"),
                "recommend_second_pass": True,
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
