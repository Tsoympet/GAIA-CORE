"""Task planner for GAIA's first orchestration pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.orchestrator.task_graph import TaskGraph, TaskGraphBuilder


class PlanStep(BaseModel):
    """Structured planner step before graph execution."""

    id: str
    objective: str
    required_capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    rationale: str


class TaskPlan(BaseModel):
    """Planner output before execution."""

    objective: str
    summary: str
    steps: list[PlanStep] = Field(default_factory=list)
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
        steps = self._create_steps(normalized, requested, explicit=bool(capabilities))
        graph = self.graph_builder.build_from_steps(normalized, steps)
        return TaskPlan(
            objective=normalized,
            summary="Create a safe structured execution plan for the bootstrap runtime.",
            steps=steps,
            graph=graph,
            assumptions=["No external actions are executed by the bootstrap planner."],
        )

    def _create_steps(
        self, objective: str, capabilities: list[str], *, explicit: bool
    ) -> list[PlanStep]:
        """Create deterministic HuggingGPT-style task steps for the bootstrap planner."""
        primary = capabilities or ["reasoning"]
        if explicit:
            return [
                PlanStep(
                    id="step-1",
                    objective=objective,
                    required_capabilities=primary,
                    rationale=(
                        "User supplied explicit capabilities; execute one focused routed step."
                    ),
                )
            ]
        return [
            PlanStep(
                id="step-1",
                objective=f"Plan approach for: {objective}",
                required_capabilities=["planning"],
                rationale="Decompose the objective before selecting execution capabilities.",
            ),
            PlanStep(
                id="step-2",
                objective=objective,
                required_capabilities=primary,
                dependencies=["step-1"],
                rationale="Execute the primary user objective with inferred capabilities.",
            ),
            PlanStep(
                id="step-3",
                objective=f"Reflect on result quality for: {objective}",
                required_capabilities=["reflection"],
                dependencies=["step-2"],
                rationale="Review uncertainty and limitations before final response.",
            ),
        ]

    def _infer_capabilities(self, objective: str) -> list[str]:
        lowered = objective.lower()
        if any(word in lowered for word in ("code", "test", "bug", "repository")):
            return ["coding"]
        if any(word in lowered for word in ("research", "compare", "study")):
            return ["research"]
        if any(word in lowered for word in ("memory", "remember", "recall")):
            return ["memory"]
        return ["reasoning"]
