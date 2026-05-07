"""Result aggregation and reflection helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any

from .execution_state import ExecutionState
from .task_graph import TaskGraph
from .task_node import TaskStatus

ReflectionPass = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class FinalResponse:
    """Structured final response emitted by the orchestrator."""

    answer: str
    results: dict[str, Any]
    errors: dict[str, str]
    reflections: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResultAggregator:
    """Combine node outputs and optional reflection passes into one response."""

    def __init__(self, reflection_passes: list[ReflectionPass] | None = None) -> None:
        self.reflection_passes = reflection_passes or []

    async def aggregate(self, graph: TaskGraph, state: ExecutionState) -> FinalResponse:
        ordered_ids = [node.id for node in graph.topological_sort()]
        results = {
            node_id: state.records[node_id].result
            for node_id in ordered_ids
            if node_id in state.records and state.records[node_id].status is TaskStatus.SUCCEEDED
        }
        errors = {
            node_id: state.records[node_id].error or "unknown error"
            for node_id in ordered_ids
            if node_id in state.records and state.records[node_id].status is TaskStatus.FAILED
        }
        response_payload: dict[str, Any] = {
            "results": results,
            "errors": errors,
            "node_order": ordered_ids,
        }
        reflections: list[dict[str, Any]] = []
        for reflection_pass in self.reflection_passes:
            reflection = reflection_pass(response_payload)
            if isawaitable(reflection):
                reflection = await reflection
            reflections.append(dict(reflection))
            response_payload["reflections"] = reflections

        return FinalResponse(
            answer=self._compose_answer(results, errors, reflections),
            results=results,
            errors=errors,
            reflections=reflections,
            metadata={"node_order": ordered_ids},
        )

    def _compose_answer(
        self,
        results: dict[str, Any],
        errors: dict[str, str],
        reflections: list[dict[str, Any]],
    ) -> str:
        if "final_answer" in results:
            return str(results["final_answer"])
        if errors and not results:
            return "The orchestration run failed before producing results."
        if errors:
            return "The orchestration run completed with partial results and errors."
        if reflections:
            return "The orchestration run completed and reflection passes were applied."
        return "The orchestration run completed successfully."
