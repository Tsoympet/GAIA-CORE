"""Core runtime composition root for GAIA.

The runtime wires together orchestration, capability routing, agent registry,
memory, model catalog, and security policy components.  It is deliberately
small at bootstrap time, but the API is shaped for async autonomous workflows,
event subscriptions, tracing, and controlled execution rather than chat turns.
"""

from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.agents.registry import AgentRegistry, create_default_agent_registry
from gaia.capabilities.router import CapabilityRouter, create_default_capability_router
from gaia.memory.store import MemoryStore, create_memory_store
from gaia.models.catalog import ModelCatalog, create_model_catalog
from gaia.orchestrator.engine import Orchestrator, create_orchestrator
from gaia.security.policy import SecurityPolicy, create_security_policy


class RuntimeStatus(BaseModel):
    """Observable runtime status for health checks and operator tooling."""

    runtime_id: str
    state: str = "ready"
    configured: bool = True
    agents: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    local_first: bool = True


class GaiaRuntime(BaseModel):
    """GAIA runtime dependency graph."""

    runtime_id: str = Field(default_factory=lambda: str(uuid4()))
    config_dir: Path
    orchestrator: Orchestrator
    agent_registry: AgentRegistry
    capability_router: CapabilityRouter
    model_catalog: ModelCatalog
    memory_store: MemoryStore
    security_policy: SecurityPolicy

    model_config = {"arbitrary_types_allowed": True}

    def status(self) -> RuntimeStatus:
        """Return a typed status snapshot suitable for CLI and API surfaces."""
        return RuntimeStatus(
            runtime_id=self.runtime_id,
            agents=self.agent_registry.list_agent_names(),
            capabilities=[
                capability.name for capability in self.capability_router.list_capabilities()
            ],
            local_first=self.model_catalog.local_first,
        )


def create_runtime(config_dir: Path) -> GaiaRuntime:
    """Create the default GAIA runtime composition."""
    agent_registry = create_default_agent_registry()
    capability_router = create_default_capability_router(agent_registry=agent_registry)
    model_catalog = create_model_catalog()
    memory_store = create_memory_store()
    security_policy = create_security_policy()
    orchestrator = create_orchestrator(
        capability_router=capability_router,
        memory_store=memory_store,
        security_policy=security_policy,
    )
    return GaiaRuntime(
        config_dir=config_dir,
        orchestrator=orchestrator,
        agent_registry=agent_registry,
        capability_router=capability_router,
        model_catalog=model_catalog,
        memory_store=memory_store,
        security_policy=security_policy,
    )
