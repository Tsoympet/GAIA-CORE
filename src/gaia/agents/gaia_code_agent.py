"""Code agent for implementation and codebase analysis tasks."""

from __future__ import annotations

import time

from .base_agent import AgentExecutionContext, AgentMetadata, AgentPermissionError, AgentResult, BaseAgent, Permission


class GaiaCodeAgent(BaseAgent):
    """Handles code understanding, patch planning, and controlled code execution."""

    metadata = AgentMetadata(
        name="gaia_code_agent",
        description="Code analysis, implementation planning, refactoring, and test strategy.",
        tags=("code", "development", "testing"),
    )
    capabilities = frozenset({"code", "code_analysis", "implementation", "refactoring", "testing"})
    required_permissions = frozenset({Permission.READ_CONTEXT, Permission.FILESYSTEM_READ, Permission.FILESYSTEM_WRITE})

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        started_at = time.time()
        capability = "code"
        try:
            self.ensure_permissions(context)
            self.log_event("agent_started", context, capability=capability)
            output = {
                "task": context.task,
                "implementation_steps": ("inspect codebase", "plan safe changes", "modify files", "run checks"),
                "requires_code_execution": Permission.CODE_EXECUTION not in context.granted_permissions,
            }
            self.log_event("agent_completed", context, capability=capability)
            return self.success_result(context, started_at, output, capability)
        except AgentPermissionError as exc:
            return self.permission_denied_result(context, started_at, exc.missing_permissions, capability)
