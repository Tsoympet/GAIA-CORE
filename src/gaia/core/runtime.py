"""GAIA Core Runtime composition root and task submission API."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.agents.agent_registry import AgentRegistry, create_default_agent_registry
from gaia.capabilities.capability_router import CapabilityRouter, create_default_capability_router
from gaia.continuity.journal import ContinuityJournal
from gaia.continuity.store import ContinuityStore
from gaia.core.session import SessionManager
from gaia.kernel.kernel import CognitiveKernel, create_cognitive_kernel
from gaia.kernel.resource_budget import ResourceBudget
from gaia.memory.store import MemoryStore, create_memory_store
from gaia.models.catalog import ModelCatalog, create_model_catalog
from gaia.orchestrator.aggregator import AggregatedResponse
from gaia.orchestrator.engine import Orchestrator, create_orchestrator
from gaia.organism.organism import MemoryOrganism
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
    kernel_status: str = "idle"
    kernel_id: str | None = None
    continuity: str = "unavailable"
    memory_organism: str = "unavailable"


class TaskRequest(BaseModel):
    """Runtime task submission request."""

    task: str
    session_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    budget: ResourceBudget | None = None


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
    permission_manager: PermissionManager = Field(default_factory=PermissionManager)
    sessions: SessionManager = Field(default_factory=SessionManager)
    kernel: CognitiveKernel
    organism: MemoryOrganism | None = None

    model_config = {"arbitrary_types_allowed": True}

    def status(self) -> RuntimeStatus:
        """Return a typed status snapshot suitable for CLI and API surfaces."""
        kernel_state = self.kernel.status()
        return RuntimeStatus(
            runtime_id=self.runtime_id,
            agents=self.agent_registry.list_agent_names(),
            capabilities=[
                capability.name for capability in self.capability_router.list_capabilities()
            ],
            local_first=self.model_catalog.local_first,
            kernel_status=kernel_state.status.value,
            kernel_id=kernel_state.kernel_id,
            continuity=(
                "unavailable"
                if self.kernel.continuity is None
                else self.kernel.continuity.capability_status()
            ),
            memory_organism=(
                "unavailable" if self.organism is None else self.organism.capability_status()
            ),
        )

    async def submit_task(self, request: TaskRequest) -> AggregatedResponse:
        """Accept a user task through the Cognitive Kernel control plane."""
        session = await self.sessions.get_or_create(request.session_id)
        result = await self.kernel.run(
            request.task,
            session.id,
            request.capabilities,
            budget=request.budget,
            metadata=request.metadata,
        )
        if self.organism is not None:
            project_id = request.metadata.get("project_id")
            self.organism.record_kernel_outcome(
                objective=request.task,
                answer=result.response.answer,
                status=result.response.status,
                session_id=session.id,
                execution_id=result.goal.id,
                project_id=project_id if isinstance(project_id, str) else None,
            )
        return result.response


def create_runtime(
    config_dir: Path | str = Path("config"),
    *,
    continuity_path: Path | str | None = None,
    organism_path: Path | str | None = None,
) -> GaiaRuntime:
    """Create the default GAIA runtime composition."""
    agent_registry = create_default_agent_registry()
    capability_router = create_default_capability_router(agent_registry=agent_registry)
    model_catalog = create_model_catalog()
    memory_store = create_memory_store()
    security_policy = create_security_policy()
    permission_manager = PermissionManager()
    orchestrator = create_orchestrator(
        capability_router=capability_router,
        memory_store=memory_store,
        security_policy=security_policy,
        agent_registry=agent_registry,
    )
    continuity: ContinuityJournal | None = None
    if continuity_path is not None:
        store = ContinuityStore(continuity_path)
        continuity = ContinuityJournal(store, store.recover())
    kernel = create_cognitive_kernel(
        orchestrator=orchestrator,
        security_policy=security_policy,
        permission_manager=permission_manager,
        continuity=continuity,
    )
    organism = MemoryOrganism(organism_path) if organism_path is not None else None
    if organism is not None and continuity is not None:
        organism.bind_continuity(continuity.store)
    return GaiaRuntime(
        config_dir=Path(config_dir),
        orchestrator=orchestrator,
        agent_registry=agent_registry,
        capability_router=capability_router,
        model_catalog=model_catalog,
        memory_store=memory_store,
        security_policy=security_policy,
        permission_manager=permission_manager,
        kernel=kernel,
        organism=organism,
    )
