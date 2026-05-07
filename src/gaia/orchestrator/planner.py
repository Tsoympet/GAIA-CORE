"""Task planner for GAIA's first orchestration pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.orchestrator.task_graph import TaskGraph, TaskGraphBuilder


class TaskPlan(BaseModel):
    """Planner output before execution."""

    objective: str
    summary: str
    graph: TaskGraph
    assumptions: list[str] = Field(default_factory=list)


class TaskPlanner:
    """Rule-based bootstrap planner shaped for later LLM-assisted decomposition."""

    def __init__(self, graph_builder: TaskGraphBuilder | None = None) -> None:
        self.graph_builder = graph_builder or TaskGraphBuilder()

    async def create_plan(self, objective: str, capabilities: list[str] | None = None) -> TaskPlan:
        """Create a minimal DAG-backed plan for a user task."""
        normalized = objective.strip()
        if not normalized:
            raise ValueError("objective must not be empty")
        requested = capabilities or self._infer_capabilities(normalized)
        graph = self.graph_builder.build(normalized, requested)
        return TaskPlan(
            objective=normalized,
            summary="Create a safe single-step execution plan for the bootstrap runtime.",
            graph=graph,
            assumptions=["No external actions are executed by the bootstrap planner."],
        )

    def _infer_capabilities(self, objective: str) -> list[str]:
        lowered = objective.lower()
        if any(word in lowered for word in ("code", "test", "bug", "repository")):
            return ["coding"]
        if any(word in lowered for word in ("research", "compare", "study")):
            return ["research"]
        if any(word in lowered for word in ("memory", "remember", "recall")):
            return ["memory"]
        return ["reasoning"]
