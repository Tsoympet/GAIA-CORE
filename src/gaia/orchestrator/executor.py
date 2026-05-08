"""Task graph executor for GAIA agents."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.agents.agent_registry import AgentRegistry
from gaia.agents.base_agent import AgentContext, AgentResult
from gaia.capabilities.capability_router import CapabilityRouter, RouteDecision
from gaia.orchestrator.task_graph import TaskGraph, TaskNode


class NodeExecutionResult(BaseModel):
    """Execution result for one task graph node."""

    node_id: str
    route: RouteDecision
    result: AgentResult


class ExecutionReport(BaseModel):
    """Complete execution report for a task graph."""

    graph_id: str
    node_results: list[NodeExecutionResult] = Field(default_factory=list)


class MultiAgentExecutor:
    """Executes task graph nodes by routing to registered agents."""

    def __init__(self, agent_registry: AgentRegistry, capability_router: CapabilityRouter) -> None:
        self.agent_registry = agent_registry
        self.capability_router = capability_router

    async def execute(self, graph: TaskGraph, session_id: str) -> ExecutionReport:
        """Execute all graph nodes in dependency order."""
        report = ExecutionReport(graph_id=graph.id)
        for node in graph.execution_order():
            report.node_results.append(await self.execute_node(node, session_id))
        return report

    async def execute_node(self, node: TaskNode, session_id: str) -> NodeExecutionResult:
        """Route and execute a single node."""
        node.execution_status = "running"
        route = self.capability_router.route(node.required_capabilities)
        node.assigned_agent = route.selected_agent
        node.assigned_model = route.selected_model
        node.assigned_tool = route.selected_tool
        node.execution_mode = route.execution_mode
        agent = self.agent_registry.get(route.selected_agent)
        context = AgentContext(session_id=session_id, task_id=node.id)
        try:
            result = await agent.run(node.objective, context)
        except Exception:
            node.execution_status = "failed"
            raise
        node.execution_status = "completed"
        node.result = result.model_dump(mode="json")
        return NodeExecutionResult(node_id=node.id, route=route, result=result)
