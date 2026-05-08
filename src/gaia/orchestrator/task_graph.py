"""DAG task graph primitives for GAIA orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class TaskNode(BaseModel):
    """A single node in a GAIA execution graph."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    required_capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    assigned_agent: str | None = None
    execution_status: str = "pending"
    result: dict[str, object] = Field(default_factory=dict)


class TaskGraph(BaseModel):
    """A simple acyclic graph for auditable task execution."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    nodes: list[TaskNode] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_dependencies(self) -> TaskGraph:
        """Ensure every dependency points to a known node."""
        ids = {node.id for node in self.nodes}
        missing = [dep for node in self.nodes for dep in node.dependencies if dep not in ids]
        if missing:
            raise ValueError(f"unknown task dependencies: {missing}")
        return self

    def execution_order(self) -> list[TaskNode]:
        """Return nodes in dependency-respecting order."""
        ordered: list[TaskNode] = []
        remaining = {node.id: node for node in self.nodes}
        while remaining:
            completed = {node.id for node in ordered}
            ready = [
                node
                for node in remaining.values()
                if all(dep in completed for dep in node.dependencies)
            ]
            if not ready:
                raise ValueError("task graph contains a cycle")
            for node in sorted(ready, key=lambda item: item.id):
                ordered.append(node)
                remaining.pop(node.id)
        return ordered


class TaskGraphBuilder:
    """Build bootstrap DAGs from planner output."""

    def build(self, objective: str, capabilities: list[str]) -> TaskGraph:
        """Build a one-node DAG for the initial runnable foundation."""
        return TaskGraph(
            objective=objective,
            nodes=[
                TaskNode(
                    objective=objective,
                    required_capabilities=capabilities or ["reasoning"],
                )
            ],
        )
