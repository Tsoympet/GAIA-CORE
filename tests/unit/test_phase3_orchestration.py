from pathlib import Path

import pytest

from gaia.agents.agent_registry import AgentRegistry
from gaia.agents.base_agent import AgentContext, AgentResult, BaseAgent
from gaia.capabilities.capability_registry import (
    create_default_capability_registry,
)
from gaia.capabilities.capability_router import CapabilityRouter
from gaia.core.runtime import TaskRequest, create_runtime
from gaia.orchestrator.executor import MultiAgentExecutor
from gaia.orchestrator.planner import TaskPlanner
from gaia.orchestrator.task_graph import TaskGraph, TaskNode


@pytest.mark.asyncio
async def test_planner_produces_dependency_ordered_structured_steps() -> None:
    plan = await TaskPlanner().create_plan(
        "Research and code a local-first routing improvement",
        ["research", "coding"],
    )

    assert [step.id for step in plan.steps] == ["step-1", "step-2"]
    assert plan.steps[1].dependencies == ["step-1"]
    assert [node.id for node in plan.graph.execution_order()] == [
        "step-1",
        "step-2",
    ]


@pytest.mark.asyncio
async def test_orchestrator_plan_includes_route_metadata_for_each_step() -> None:
    runtime = create_runtime(config_dir=Path("config"))

    plan = await runtime.orchestrator.plan(
        "Research and code a local-first routing improvement",
        ["research", "coding"],
    )

    assert [route.selected_agent for route in plan.routes] == [
        "gaia_research_agent",
        "gaia_code_agent",
    ]
    assert plan.routes[1].selected_model == "local-code-reasoner"
    assert (
        plan.routes[1].selected_tool
        == "permission_checked_repo_tools"
    )
    assert plan.graph.nodes[1].execution_mode == "permission_gated"
    assert plan.routes[1].requires_human_approval is True


class CountingAgent(BaseAgent):
    name = "counting_agent"
    capabilities = ("counting",)

    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self,
        task: str,
        context: AgentContext,
    ) -> AgentResult:
        self.calls += 1
        return AgentResult(
            task_id=context.task_id,
            agent_name=self.name,
            content=task,
            confidence=1.0,
        )


@pytest.mark.asyncio
async def test_executor_invokes_each_node_exactly_once() -> None:
    agent = CountingAgent()
    registry = AgentRegistry()
    registry.register(agent)
    router = CapabilityRouter(
        create_default_capability_registry(),
        registry,
    )
    graph = TaskGraph(
        objective="Count once",
        nodes=[
            TaskNode(
                id="step-1",
                objective="Count once",
                required_capabilities=["counting"],
            )
        ],
    )

    report = await MultiAgentExecutor(registry, router).execute(
        graph,
        "session-1",
    )

    assert len(report.node_results) == 1
    assert agent.calls == 1
    assert graph.nodes[0].execution_status == "completed"


@pytest.mark.asyncio
async def test_runtime_runs_pipeline_with_reflection_and_audit_memory() -> None:
    runtime = create_runtime(config_dir=Path("config"))

    response = await runtime.submit_task(
        TaskRequest(
            task="Research and code a local-first routing improvement",
            capabilities=["research", "coding"],
        )
    )

    assert response.status == "completed"
    assert response.agents == [
        "gaia_research_agent",
        "gaia_code_agent",
    ]
    assert response.reflection is not None
    assert response.artifacts["pipeline"][-1] == "reflection_loop"
    assert response.artifacts["node_count"] == 2
    assert runtime.memory_store.events[-1].event_type == (
        "reflection_completed"
    )
