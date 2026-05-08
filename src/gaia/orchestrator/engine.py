"""Composition of planner, router, executor, aggregator, and reflection for GAIA."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from gaia.agents.agent_registry import AgentRegistry
from gaia.capabilities.capability_router import CapabilityRouter, RouteDecision
from gaia.memory.memory_manager import MemoryManager
from gaia.metacognition.reflection_loop import ReflectionLoop, ReflectionReport
from gaia.metacognition.reflection_loop import ReflectionLoop
from gaia.orchestrator.aggregator import AggregatedResponse, ResultAggregator
from gaia.orchestrator.executor import ExecutionReport, MultiAgentExecutor
from gaia.orchestrator.planner import TaskPlan, TaskPlanner, TaskStep
from gaia.security.policy import SecurityDecision, SecurityPolicy


class OrchestrationPlan(BaseModel):
    """Initial execution plan with route and security decisions."""

    graph: object
    routes: list[RouteDecision]
    security: SecurityDecision
    steps: list[TaskStep] = Field(default_factory=list)


class Orchestrator:
    """Coordinates task planning, routing, execution, aggregation, and reflection."""

    def __init__(
        self,
        planner: TaskPlanner,
        executor: MultiAgentExecutor,
        aggregator: ResultAggregator,
        capability_router: CapabilityRouter,
        memory: MemoryManager,
        security_policy: SecurityPolicy,
        reflection_loop: ReflectionLoop | None = None,
    ) -> None:
        self.planner = planner
        self.executor = executor
        self.aggregator = aggregator
        self.capability_router = capability_router
        self.memory = memory
        self.security_policy = security_policy
        self.reflection_loop = reflection_loop or ReflectionLoop()

    async def plan(self, objective: str, capabilities: Sequence[str] = ()) -> OrchestrationPlan:
        """Create a DAG plan and route every node without executing it."""
        task_plan = await self.planner.create_plan(objective, list(capabilities))
        security = self.security_policy.evaluate_objective(objective)
        routes = [
            self.capability_router.route(node.required_capabilities)
            for node in task_plan.graph.nodes
        ]
        await self.memory.remember(
            "plan_created",
            objective,
            {"graph_id": task_plan.graph.id, "step_count": len(task_plan.steps)},
        )
        return OrchestrationPlan(
            graph=task_plan.graph,
            routes=routes,
            security=security,
            steps=task_plan.steps,
        )

    async def run(
        self, objective: str, session_id: str, capabilities: Sequence[str] = ()
    ) -> AggregatedResponse:
        """Run planner-router-executor-aggregator-reflection pipeline."""
        task_plan: TaskPlan = await self.planner.create_plan(objective, list(capabilities))
        security = self.security_policy.evaluate_objective(objective)
        if not security.allowed:
            await self.memory.remember("security_block", objective, {"reasons": security.reasons})
            return AggregatedResponse(
                task_id=task_plan.graph.id,
                status="blocked",
                answer="Task blocked by GAIA security policy.",
                confidence=1.0,
                artifacts={"security": security.model_dump(mode="json")},
            )
        report: ExecutionReport = await self.executor.execute(task_plan.graph, session_id)
        response = await self.aggregator.aggregate(objective, report)
        reflection = self._reflect(response, report)
        response.artifacts["reflection"] = reflection.model_dump(mode="json")
        response.artifacts["pipeline"] = [
            "planner",
            "task_graph",
            "capability_router",
            "agent_executor",
            "result_aggregator",
            "reflection_pass",
            "final_response",
        ]
        reflection = self.reflection_loop.review(
            response.answer,
            {
                "agent_confidence": response.confidence,
                "node_completion": 1.0 if response.status == "completed" else 0.0,
                "route_coverage": min(
                    1.0,
                    len(report.node_results) / max(1, len(task_plan.graph.nodes)),
                ),
            },
        )
        response.confidence = min(response.confidence, reflection.confidence.confidence)
        response.artifacts["reflection"] = reflection.model_dump(mode="json")
        await self.memory.remember(
            "task_completed",
            objective,
            {
                "graph_id": task_plan.graph.id,
                "agents": response.agents,
                "confidence": response.confidence,
                "reflection_confidence": reflection.confidence.confidence,
            },
        )
        await self.memory.remember(
            "reflection_completed",
            objective,
            {
                "graph_id": task_plan.graph.id,
                "confidence": response.confidence,
                "uncertainty": reflection.confidence.uncertainty,
            },
        )
        return response

    def _reflect(
        self, response: AggregatedResponse, report: ExecutionReport
    ) -> ReflectionReport:
        node_count = max(1, len(report.node_results))
        completed = len(report.node_results)
        route_score = sum(1 for node in report.node_results if node.route.selected_agent)
        signals = {
            "agent_confidence": response.confidence,
            "completion": completed / node_count,
            "routing": route_score / node_count,
        }
        return self.reflection_loop.review(response.answer, signals)


def create_orchestrator(
    capability_router: CapabilityRouter,
    memory_store: MemoryManager,
    security_policy: SecurityPolicy,
    agent_registry: AgentRegistry | None = None,
) -> Orchestrator:
    """Create a GAIA orchestrator instance."""
    if agent_registry is None:
        # Compatibility path; prefer passing the same registry used by the runtime.
        from gaia.agents.agent_registry import create_default_agent_registry

        agent_registry = create_default_agent_registry()
    return Orchestrator(
        planner=TaskPlanner(),
        executor=MultiAgentExecutor(agent_registry, capability_router),
        aggregator=ResultAggregator(),
        capability_router=capability_router,
        memory=memory_store,
        security_policy=security_policy,
    )
