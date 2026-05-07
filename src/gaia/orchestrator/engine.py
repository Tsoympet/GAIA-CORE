"""Async orchestration primitives for GAIA task graphs."""

from collections.abc import Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.capabilities.router import CapabilityRouter, RouteDecision
from gaia.memory.store import MemoryStore
from gaia.security.policy import SecurityDecision, SecurityPolicy


class TaskNode(BaseModel):
    """A unit of work in an orchestration DAG."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    required_capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class TaskGraph(BaseModel):
    """A DAG representation used for autonomous, auditable workflows."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    nodes: list[TaskNode] = Field(default_factory=list)


class OrchestrationPlan(BaseModel):
    """Initial execution plan with route and security decisions."""

    graph: TaskGraph
    routes: list[RouteDecision]
    security: SecurityDecision


class Orchestrator(BaseModel):
    """Coordinates task decomposition, capability routing, and safe execution."""

    capability_router: CapabilityRouter
    memory_store: MemoryStore
    security_policy: SecurityPolicy

    model_config = {"arbitrary_types_allowed": True}

    async def plan(self, objective: str, capabilities: Sequence[str] = ()) -> OrchestrationPlan:
        """Create a minimal task graph and route it through GAIA capabilities."""
        node = TaskNode(objective=objective, required_capabilities=list(capabilities))
        graph = TaskGraph(objective=objective, nodes=[node])
        security = self.security_policy.evaluate_objective(objective)
        routes = [self.capability_router.route(node.required_capabilities)]
        await self.memory_store.record_event(
            "plan_created",
            {"graph_id": graph.id, "objective": objective},
        )
        return OrchestrationPlan(graph=graph, routes=routes, security=security)


def create_orchestrator(
    capability_router: CapabilityRouter,
    memory_store: MemoryStore,
    security_policy: SecurityPolicy,
) -> Orchestrator:
    """Create an orchestrator instance."""
    return Orchestrator(
        capability_router=capability_router,
        memory_store=memory_store,
        security_policy=security_policy,
    )
