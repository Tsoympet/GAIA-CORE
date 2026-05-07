"""Request planner for GAIA's orchestration workflow.

The planner follows the high-level pattern:
User Request → Task Planning → Capability Selection → Task Execution → Result
Aggregation → Final Answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .task_graph import TaskGraph
from .task_node import CapabilityRequirement, RetryPolicy, TaskNode


@dataclass(frozen=True, slots=True)
class PlanningOptions:
    default_timeout_seconds: float | None = 120.0
    default_retry_policy: RetryPolicy = RetryPolicy(max_attempts=2, backoff_seconds=0.25)
    enable_reflection: bool = True


class RequestPlanner:
    """Convert a user request into a structured task graph.

    This first implementation is deterministic and conservative. It creates a
    graph that can be replaced later by an LLM planner while preserving the
    same typed task-node contract.
    """

    def __init__(self, options: PlanningOptions | None = None) -> None:
        self.options = options or PlanningOptions()

    def plan(self, user_request: str) -> TaskGraph:
        if not user_request.strip():
            raise ValueError("user_request cannot be empty")

        nodes = [
            self._node(
                "task_planning",
                "Decompose the user request into actionable sub-goals.",
                capabilities=["planning", "reasoning"],
                metadata={"user_request": user_request},
            ),
            self._node(
                "capability_selection",
                "Select agents, tools, or models that satisfy each sub-goal.",
                dependencies={"task_planning"},
                capabilities=["routing", "capability_selection"],
            ),
            self._node(
                "task_execution",
                "Execute the selected task plan with routed capabilities.",
                dependencies={"capability_selection"},
                capabilities=["execution"],
            ),
            self._node(
                "result_aggregation",
                "Aggregate intermediate task results into a coherent response.",
                dependencies={"task_execution"},
                capabilities=["aggregation", "summarization"],
            ),
        ]

        final_dependencies = {"result_aggregation"}
        if self.options.enable_reflection:
            nodes.append(
                self._node(
                    "reflection",
                    "Review aggregated results for gaps, errors, and answer quality.",
                    dependencies={"result_aggregation"},
                    capabilities=["reflection", "critique"],
                )
            )
            final_dependencies = {"reflection"}

        nodes.append(
            self._node(
                "final_answer",
                "Produce the final answer for the user.",
                dependencies=final_dependencies,
                capabilities=["response_generation"],
            )
        )
        return TaskGraph(nodes)

    def _node(
        self,
        node_id: str,
        description: str,
        *,
        dependencies: set[str] | None = None,
        capabilities: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> TaskNode:
        return TaskNode(
            id=node_id,
            description=description,
            dependencies=dependencies or set(),
            capability=CapabilityRequirement.from_values(capabilities),
            retry_policy=self.options.default_retry_policy,
            timeout_seconds=self.options.default_timeout_seconds,
            metadata=dict(metadata or {}),
        )
