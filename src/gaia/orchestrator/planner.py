"""Deterministic task planning for GAIA's local-first orchestration pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.orchestrator.task_graph import TaskGraph, TaskGraphBuilder


class TaskStep(BaseModel):
    """A structured planner step before graph execution."""

    id: str
    objective: str
    required_capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    execution_hint: str = "local"


class TaskPlan(BaseModel):
    """Planner output before execution."""

    objective: str
    summary: str
    steps: list[TaskStep] = Field(default_factory=list)
    graph: TaskGraph
    assumptions: list[str] = Field(default_factory=list)


class TaskPlanner:
    """Rule-based bootstrap planner for later model-assisted decomposition."""

    def __init__(self, graph_builder: TaskGraphBuilder | None = None) -> None:
        self.graph_builder = graph_builder or TaskGraphBuilder()

    async def create_plan(
        self,
        objective: str,
        capabilities: list[str] | None = None,
    ) -> TaskPlan:
        """Create a dependency-ordered, DAG-backed plan for a user task."""
        normalized = objective.strip()
        if not normalized:
            raise ValueError("objective must not be empty")

        inferred = capabilities or self._infer_capabilities(normalized)
        requested = self._deduplicate(inferred)
        steps = self._build_steps(normalized, requested)
        graph = self.graph_builder.build_from_steps(normalized, steps)

        return TaskPlan(
            objective=normalized,
            summary=(
                "Create a safe local-first execution plan with structured steps, "
                "capability routing, result aggregation, and reflection."
            ),
            steps=steps,
            graph=graph,
            assumptions=[
                "The bootstrap planner performs no external actions.",
                "Risky actions remain permission-gated by GAIA security policy.",
            ],
        )

    def _build_steps(
        self,
        objective: str,
        capabilities: list[str],
    ) -> list[TaskStep]:
        """Convert capabilities into deterministic dependency-ordered steps."""
        steps: list[TaskStep] = []
        previous_id: str | None = None

        for index, capability in enumerate(
            capabilities or ["reasoning"],
            start=1,
        ):
            step_id = f"step-{index}"
            step_objective = (
                objective
                if len(capabilities) == 1
                else f"{objective} [{capability}]"
            )
            steps.append(
                TaskStep(
                    id=step_id,
                    objective=step_objective,
                    required_capabilities=[capability],
                    dependencies=[previous_id] if previous_id else [],
                    execution_hint=self._execution_hint(capability),
                )
            )
            previous_id = step_id

        return steps

    def _execution_hint(self, capability: str) -> str:
        """Return a safe execution hint for the router and executor."""
        if capability in {
            "coding",
            "repo",
            "tooling",
            "plugins",
            "self_evolve",
        }:
            return "permission_gated"
        if capability in {"voice", "audio", "speech", "tts", "stt"}:
            return "local_with_text_fallback"
        return "local"

    def _infer_capabilities(self, objective: str) -> list[str]:
        """Infer a small capability set without invoking a model."""
        lowered = objective.lower()
        capabilities: list[str] = []

        if any(
            word in lowered
            for word in ("research", "compare", "study", "source")
        ):
            capabilities.append("research")
        if any(
            word in lowered
            for word in ("code", "test", "bug", "repository", "software")
        ):
            capabilities.append("coding")
        if any(
            word in lowered
            for word in ("memory", "remember", "recall")
        ):
            capabilities.append("memory")
        if any(
            word in lowered
            for word in ("voice", "speak", "audio", "transcribe")
        ):
            capabilities.append("voice")
        if any(
            word in lowered
            for word in ("secure", "permission", "policy", "risk")
        ):
            capabilities.append("security")

        return capabilities or ["reasoning"]

    def _deduplicate(self, capabilities: list[str]) -> list[str]:
        """Normalize capabilities while preserving first-seen order."""
        deduplicated: list[str] = []
        for capability in capabilities:
            normalized = capability.strip().lower()
            if normalized and normalized not in deduplicated:
                deduplicated.append(normalized)
        return deduplicated or ["reasoning"]
