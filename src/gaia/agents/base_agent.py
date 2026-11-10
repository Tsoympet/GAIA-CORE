"""Base agent contracts for GAIA's local-first multi-agent runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.models.local_client import DETERMINISTIC_MODEL_ID, LocalModelClient


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

    name: str = "gaia_core_agent"
    description: str = "General local-first reasoning and task synthesis agent."
    capabilities: tuple[str, ...] = ("reasoning", "planning")

    async def run(self, task: str, context: AgentContext) -> AgentResult:
        """Return a structured local plan without calling a remote model."""
        content = await _local_plan(task, self.capabilities)
        return AgentResult(
            task_id=context.task_id,
            agent_name=self.name,
            content=content,
            confidence=0.64,
            artifacts={
                "mode": "deterministic_local",
                "model_id": DETERMINISTIC_MODEL_ID,
                "provider": "local",
                "neural_weights_loaded": False,
                "session_id": context.session_id,
            },
        )


class CapabilityAgent(LocalReasoningAgent):
    """Capability-specialized agent with deterministic bootstrap behavior."""

    def __init__(
        self,
        name: str,
        description: str,
        capabilities: tuple[str, ...],
    ) -> None:
        self.name = name
        self.description = description
        self.capabilities = capabilities

    async def run(self, task: str, context: AgentContext) -> AgentResult:
        content = await _local_plan(task, self.capabilities)
        return AgentResult(
            task_id=context.task_id,
            agent_name=self.name,
            content=content,
            confidence=0.58,
            artifacts={
                "mode": "deterministic_local",
                "model_id": DETERMINISTIC_MODEL_ID,
                "provider": "local",
                "neural_weights_loaded": False,
                "capabilities": list(self.capabilities),
            },
        )


async def _local_plan(task: str, capabilities: tuple[str, ...]) -> str:
    focus = ", ".join(capabilities) if capabilities else "reasoning"
    return await LocalModelClient().generate(
        f"{task}\ncapabilities: {focus}",
        DETERMINISTIC_MODEL_ID,
    )
