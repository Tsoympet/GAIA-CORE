"""Dependency resolution helpers for task execution."""

from __future__ import annotations

from .task_graph import TaskGraph
from .task_node import TaskStatus


class DependencyResolver:
    """Find executable task nodes from graph structure and execution state."""

    def __init__(self, graph: TaskGraph) -> None:
        self.graph = graph
        self.graph.validate()

    def executable_nodes(self, completed: set[str], blocked: set[str] | None = None) -> list[str]:
        blocked = blocked or set()
        executable: list[str] = []
        for node in self.graph.topological_sort():
            if node.id in completed or node.id in blocked:
                continue
            if node.dependencies <= completed:
                executable.append(node.id)
        return executable

    def blocked_by_failed_dependencies(self, failed: set[str]) -> set[str]:
        blocked: set[str] = set()
        changed = True
        while changed:
            changed = False
            for node in self.graph:
                if node.id in blocked or node.id in failed:
                    continue
                if node.dependencies & (failed | blocked):
                    blocked.add(node.id)
                    changed = True
        return blocked

    def statuses_ready_for_execution(self, statuses: dict[str, TaskStatus]) -> list[str]:
        completed = {
            node_id
            for node_id, status in statuses.items()
            if status is TaskStatus.SUCCEEDED
        }
        terminal_failures = {
            node_id
            for node_id, status in statuses.items()
            if status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.SKIPPED}
        }
        blocked = terminal_failures | self.blocked_by_failed_dependencies(terminal_failures)
        return self.executable_nodes(completed, blocked)
