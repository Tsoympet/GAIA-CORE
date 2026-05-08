"""Task planner for GAIA's JARVIS-style orchestration pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.orchestrator.task_graph import TaskGraph, TaskGraphBuilder, TaskNode


class TaskStep(BaseModel):
    """Structured planner step before conversion to a task graph node."""

    id: str
    title: str
    objective: str
    required_capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    expected_output: str = "structured result"


class TaskPlan(BaseModel):
    """Planner output before execution."""

    objective: str
    summary: str
    graph: TaskGraph
    steps: list[TaskStep] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class TaskPlanner:
    """Rule-based bootstrap planner shaped for later LLM-assisted decomposition."""

    def __init__(self, graph_builder: TaskGraphBuilder | None = None) -> None:
        self.graph_builder = graph_builder or TaskGraphBuilder()

    async def create_plan(self, objective: str, capabilities: list[str] | None = None) -> TaskPlan:
        """Create a DAG-backed plan for a user task."""
        normalized = objective.strip()
        if not normalized:
            raise ValueError("objective must not be empty")
        requested = capabilities or self._infer_capabilities(normalized)
        steps = self._build_steps(normalized, requested)
        graph = self.graph_builder.build_from_steps(normalized, steps)
        return TaskPlan(
            objective=normalized,
            summary=(
                "Create a safe local-first execution plan using planner, task graph, "
                "capability routing, agent execution, aggregation, and reflection."
            ),
            graph=graph,
            steps=steps,
            assumptions=[
                "External actions remain disabled unless a later permission gate approves them.",
                "Model/tool choices are local-first bootstrap routing hints.",
            ],
        )

    def _infer_capabilities(self, objective: str) -> list[str]:
        lowered = objective.lower()
        inferred: list[str] = []
        if any(word in lowered for word in ("code", "test", "bug", "repository")):
            inferred.append("coding")
        if any(word in lowered for word in ("research", "compare", "study")):
            inferred.append("research")
        if any(word in lowered for word in ("memory", "remember", "recall")):
            inferred.append("memory")
        if any(word in lowered for word in ("secure", "permission", "policy", "risk")):
            inferred.append("security")
        if any(word in lowered for word in ("voice", "speak", "speech", "audio")):
            inferred.append("voice")
        return inferred or ["reasoning"]

    def _build_steps(self, objective: str, capabilities: list[str]) -> list[TaskStep]:
        unique_capabilities = self._dedupe(capabilities) or ["reasoning"]
        steps: list[TaskStep] = []
        previous_id: str | None = None
        for index, capability in enumerate(unique_capabilities, start=1):
            step_id = f"step-{index}"
            steps.append(
                TaskStep(
                    id=step_id,
                    title=f"Route {capability} work",
                    objective=self._step_objective(objective, capability),
                    required_capabilities=[capability],
                    dependencies=[previous_id] if previous_id else [],
                    expected_output=f"{capability} agent result",
                )
            )
            previous_id = step_id
        if len(steps) > 1:
            steps.append(
                TaskStep(
                    id=f"step-{len(steps) + 1}",
                    title="Synthesize multi-agent findings",
                    objective=f"Synthesize results for: {objective}",
                    required_capabilities=["reasoning"],
                    dependencies=[previous_id] if previous_id else [],
                    expected_output="final synthesis",
                )
            )
        return steps

    def _step_objective(self, objective: str, capability: str) -> str:
        if capability == "reasoning":
            return objective
        return f"Use {capability} capability to address: {objective}"

    def _dedupe(self, capabilities: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for capability in capabilities:
            normalized = capability.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered


def steps_to_nodes(steps: list[TaskStep]) -> list[TaskNode]:
    """Convert planner steps into task graph nodes."""
    return [
        TaskNode(
            id=step.id,
            objective=step.objective,
            title=step.title,
            required_capabilities=step.required_capabilities,
            dependencies=step.dependencies,
            expected_output=step.expected_output,
        )
        for step in steps
    ]
