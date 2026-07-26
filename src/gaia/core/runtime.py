"""GAIA Core Runtime composition root and task submission API."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.agents.agent_registry import (
    AgentRegistry,
    create_default_agent_registry,
)
from gaia.capabilities.capability_router import (
    CapabilityRouter,
    create_default_capability_router,
)
from gaia.core.session import SessionManager
from gaia.kernel import (
    CognitiveKernel,
    InMemoryKernelStore,
    KernelBudgetError,
    KernelCancelledError,
    KernelStatus,
    KernelTimeoutError,
    ResourceBudget,
    SQLiteKernelStore,
)
from gaia.memory.store import MemoryStore, create_memory_store
from gaia.models.catalog import ModelCatalog, create_model_catalog
from gaia.orchestrator.aggregator import AggregatedResponse
from gaia.orchestrator.engine import Orchestrator, create_orchestrator
from gaia.security.permission_manager import PermissionManager
from gaia.security.policy import SecurityPolicy, create_security_policy


class RuntimeStatus(BaseModel):
    """Observable runtime status for health checks and operator tooling."""

    runtime_id: str
    state: str = "ready"
    configured: bool = True
    agents: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    local_first: bool = True
    kernel: KernelStatus = Field(default_factory=KernelStatus)


class TaskRequest(BaseModel):
    """Runtime task submission request."""

    task: str
    session_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    goal_id: str | None = None
    budget: ResourceBudget = Field(default_factory=ResourceBudget)


class JsonFormatter(logging.Formatter):
    """Minimal structured log formatter for runtime logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, default=str)


class GaiaRuntime(BaseModel):
    """GAIA runtime dependency graph for local-first execution."""

    runtime_id: str = Field(default_factory=lambda: str(uuid4()))
    config_dir: Path
    orchestrator: Orchestrator
    agent_registry: AgentRegistry
    capability_router: CapabilityRouter
    model_catalog: ModelCatalog
    memory_store: MemoryStore
    security_policy: SecurityPolicy
    permission_manager: PermissionManager = Field(
        default_factory=PermissionManager
    )
    sessions: SessionManager = Field(default_factory=SessionManager)
    kernel: CognitiveKernel = Field(default_factory=CognitiveKernel)

    model_config = {"arbitrary_types_allowed": True}

    def status(self) -> RuntimeStatus:
        """Return a typed status snapshot suitable for CLI and API surfaces."""
        return RuntimeStatus(
            runtime_id=self.runtime_id,
            agents=self.agent_registry.list_agent_names(),
            capabilities=[
                capability.name
                for capability in self.capability_router.list_capabilities()
            ],
            local_first=self.model_catalog.local_first,
            kernel=self.kernel.status(),
        )

    async def submit_task(self, request: TaskRequest) -> AggregatedResponse:
        """Execute a task through Cognitive Kernel governance."""
        session = await self.sessions.get_or_create(request.session_id)
        try:
            execution = self.kernel.begin_execution(
                objective=request.task,
                session_id=session.id,
                capabilities=request.capabilities,
                goal_id=request.goal_id,
                budget=request.budget,
                metadata=request.metadata,
            )
        except KernelBudgetError as exc:
            return self._kernel_failure_response(
                status="blocked",
                reason=str(exc),
            )

        async def operation() -> AggregatedResponse:
            return await self.orchestrator.run(
                request.task,
                session.id,
                request.capabilities,
            )

        try:
            return await self.kernel.run_guarded(
                execution.execution_id,
                operation,
            )
        except KernelCancelledError as exc:
            return self._kernel_failure_response(
                status="cancelled",
                reason=str(exc),
                execution_id=execution.execution_id,
                goal_id=execution.goal_id,
            )
        except KernelTimeoutError as exc:
            return self._kernel_failure_response(
                status="timed_out",
                reason=str(exc),
                execution_id=execution.execution_id,
                goal_id=execution.goal_id,
            )
        except KernelBudgetError as exc:
            return self._kernel_failure_response(
                status="failed",
                reason=str(exc),
                execution_id=execution.execution_id,
                goal_id=execution.goal_id,
            )
        except Exception as exc:
            self.kernel.mark_failed(execution.execution_id, str(exc))
            raise

    def _kernel_failure_response(
        self,
        *,
        status: str,
        reason: str,
        execution_id: str | None = None,
        goal_id: str | None = None,
    ) -> AggregatedResponse:
        return AggregatedResponse(
            task_id=execution_id or str(uuid4()),
            status=status,
            answer=f"Task {status} by the GAIA Cognitive Kernel: {reason}",
            confidence=1.0,
            artifacts={
                "kernel": {
                    "execution_id": execution_id,
                    "goal_id": goal_id,
                    "status": status,
                    "reason": reason,
                }
            },
        )


def create_runtime(
    config_dir: Path | str = Path("config"),
    kernel_store_path: Path | str | None = None,
) -> GaiaRuntime:
    """Create the default GAIA runtime composition."""
    agent_registry = create_default_agent_registry()
    capability_router = create_default_capability_router(
        agent_registry=agent_registry
    )
    model_catalog = create_model_catalog()
    memory_store = create_memory_store()
    security_policy = create_security_policy()
    configured_store = kernel_store_path or os.getenv("GAIA_KERNEL_DB")
    kernel_store = (
        SQLiteKernelStore(configured_store)
        if configured_store is not None
        else InMemoryKernelStore()
    )
    orchestrator = create_orchestrator(
        capability_router=capability_router,
        memory_store=memory_store,
        security_policy=security_policy,
        agent_registry=agent_registry,
    )
    return GaiaRuntime(
        config_dir=Path(config_dir),
        orchestrator=orchestrator,
        agent_registry=agent_registry,
        capability_router=capability_router,
        model_catalog=model_catalog,
        memory_store=memory_store,
        security_policy=security_policy,
        kernel=CognitiveKernel(store=kernel_store),
    )
