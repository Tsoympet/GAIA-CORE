"""Base agent contracts for GAIA's local-first multi-agent runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Execution context passed to agents by the orchestrator."""

    session_id: str
    task_id: str
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Structured result returned by every GAIA agent."""

    task_id: str
    agent_name: str
    content: str
    confidence: float = 0.5
    artifacts: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BaseAgent(ABC):
    """Abstract base class for specialized GAIA agents."""

    name: str = "base_agent"
    description: str = "Base GAIA agent."
    capabilities: tuple[str, ...] = ("reasoning",)
    requires_human_approval: bool = False

    @abstractmethod
    async def run(self, task: str, context: AgentContext) -> AgentResult:
        """Execute a task and return a structured result."""


class LocalReasoningAgent(BaseAgent):
    """Deterministic bootstrap agent used before model backends are wired in."""

    name = "gaia_core_agent"
    description = "General local-first reasoning and task synthesis agent."
    capabilities = ("reasoning", "planning")

    async def run(self, task: str, context: AgentContext) -> AgentResult:
        """Return a safe, deterministic response for the first runnable core."""
        return AgentResult(
            task_id=context.task_id,
            agent_name=self.name,
            content=f"GAIA bootstrap agent received and analyzed: {task}",
            confidence=0.62,
            artifacts={"mode": "local_bootstrap", "session_id": context.session_id},
        )


class CapabilityAgent(LocalReasoningAgent):
    """Simple capability-specialized agent descriptor with deterministic behavior."""

    def __init__(self, name: str, description: str, capabilities: tuple[str, ...]) -> None:
        self.name = name
        self.description = description
        self.capabilities = capabilities

    async def run(self, task: str, context: AgentContext) -> AgentResult:
        return AgentResult(
            task_id=context.task_id,
            agent_name=self.name,
            content=(
                f"{self.name} handled the task using capabilities "
                f"{', '.join(self.capabilities)}: {task}"
            ),
            confidence=0.58,
            artifacts={"capabilities": list(self.capabilities)},
        )
