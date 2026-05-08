"""Task planner for GAIA's first orchestration pipeline."""

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
    """Rule-based bootstrap planner shaped for later LLM-assisted decomposition."""

    def __init__(self, graph_builder: TaskGraphBuilder | None = None) -> None:
        self.graph_builder = graph_builder or TaskGraphBuilder()

    async def create_plan(self, objective: str, capabilities: list[str] | None = None) -> TaskPlan:
        """Create a minimal DAG-backed plan for a user task."""
        normalized = objective.strip()
        if not normalized:
            raise ValueError("objective must not be empty")
        requested = self._deduplicate(capabilities or self._infer_capabilities(normalized))
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
                "No external actions are executed by the bootstrap planner.",
                "Risky actions remain permission-gated by GAIA security policy.",
            ],
        )

    def _build_steps(self, objective: str, capabilities: list[str]) -> list[TaskStep]:
        """Convert inferred capabilities into dependency-ordered planner steps."""
        if not capabilities:
            capabilities = ["reasoning"]
        steps: list[TaskStep] = []
        previous_id: str | None = None
        for index, capability in enumerate(capabilities, start=1):
            step_id = f"step-{index}"
            step_objective = objective if len(capabilities) == 1 else f"{objective} [{capability}]"
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
        """Return a safe execution hint for the router/executor layer."""
        if capability in {"coding", "repo", "tooling"}:
            return "permission_gated"
        if capability in {"voice", "audio", "speech", "tts", "stt"}:
            return "local_with_text_fallback"
        return "local"

    def _infer_capabilities(self, objective: str) -> list[str]:
        lowered = objective.lower()
        capabilities: list[str] = []
        if any(word in lowered for word in ("research", "compare", "study")):
            capabilities.append("research")
        if any(word in lowered for word in ("code", "test", "bug", "repository")):
            capabilities.append("coding")
        if any(word in lowered for word in ("memory", "remember", "recall")):
            capabilities.append("memory")
        if any(word in lowered for word in ("voice", "speak", "audio", "transcribe")):
            capabilities.append("voice")
        return capabilities or ["reasoning"]

    def _deduplicate(self, capabilities: list[str]) -> list[str]:
        """Preserve capability order while removing duplicates and blanks."""
        deduped: list[str] = []
        for capability in capabilities:
            normalized = capability.strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return deduped or ["reasoning"]
