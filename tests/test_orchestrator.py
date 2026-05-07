"""Tests for GAIA orchestration primitives."""

from __future__ import annotations

import asyncio
import unittest

from gaia.orchestrator import (
    CapabilityRequirement,
    CapabilityRouter,
    OrchestrationExecutor,
    RequestPlanner,
    ResultAggregator,
    RouteTarget,
    TaskGraph,
    TaskNode,
    TaskStatus,
)


ALL_CAPABILITIES = frozenset(
    {
        "aggregation",
        "capability_selection",
        "critique",
        "execution",
        "planning",
        "reasoning",
        "reflection",
        "response_generation",
        "routing",
        "summarization",
    }
)


async def echo_runner(node: TaskNode, context: dict[str, object]) -> str:
    return f"{context.get('prefix', 'ran')}:{node.id}"


class OrchestratorTests(unittest.TestCase):
    def test_planner_builds_expected_workflow(self) -> None:
        graph = RequestPlanner().plan("Summarize this project")

        self.assertEqual(
            [node.id for node in graph.topological_sort()],
            [
                "task_planning",
                "capability_selection",
                "task_execution",
                "result_aggregation",
                "reflection",
                "final_answer",
            ],
        )
        self.assertEqual(graph.get("final_answer").dependencies, {"reflection"})

    def test_graph_rejects_cycles(self) -> None:
        graph = TaskGraph()
        graph.add_node(TaskNode("a", "A", dependencies={"b"}))
        graph.add_node(TaskNode("b", "B", dependencies={"a"}))

        with self.assertRaises(ValueError):
            graph.validate()

    def test_parallel_executor_and_aggregator(self) -> None:
        async def scenario() -> None:
            graph = RequestPlanner().plan("Create a plan")
            router = CapabilityRouter(
                [RouteTarget("test-agent", "agent", ALL_CAPABILITIES, echo_runner)]
            )

            state = await OrchestrationExecutor(router).execute_parallel(
                graph,
                context={"prefix": "ok"},
            )
            response = await ResultAggregator().aggregate(graph, state)

            self.assertTrue(state.is_terminal)
            self.assertEqual(state.failed_ids, set())
            self.assertEqual(state.records["final_answer"].status, TaskStatus.SUCCEEDED)
            self.assertEqual(response.answer, "ok:final_answer")

        asyncio.run(scenario())

    def test_router_requires_capabilities(self) -> None:
        router = CapabilityRouter(
            [RouteTarget("planner", "agent", frozenset({"planning"}), echo_runner)]
        )
        node = TaskNode(
            "needs-code",
            "Needs code execution",
            capability=CapabilityRequirement.from_values(["code_execution"]),
        )

        with self.assertRaises(LookupError):
            router.select(node)


if __name__ == "__main__":
    unittest.main()
