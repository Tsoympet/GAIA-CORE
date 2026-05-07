"""Directed acyclic graph container for orchestrated task nodes."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator

from .task_node import TaskNode


class TaskGraph:
    """A validated DAG of :class:`TaskNode` instances."""

    def __init__(self, nodes: Iterable[TaskNode] | None = None) -> None:
        self._nodes: dict[str, TaskNode] = {}
        for node in nodes or ():
            self.add_node(node)
        self.validate()

    def add_node(self, node: TaskNode) -> None:
        if node.id in self._nodes:
            raise ValueError(f"duplicate task node id: {node.id}")
        self._nodes[node.id] = node

    def get(self, node_id: str) -> TaskNode:
        return self._nodes[node_id]

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def __iter__(self) -> Iterator[TaskNode]:
        return iter(self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def node_ids(self) -> set[str]:
        return set(self._nodes)

    def dependencies_of(self, node_id: str) -> set[str]:
        return set(self.get(node_id).dependencies)

    def dependents_of(self, node_id: str) -> set[str]:
        return {node.id for node in self if node_id in node.dependencies}

    def roots(self) -> list[TaskNode]:
        return [node for node in self if not node.dependencies]

    def leaves(self) -> list[TaskNode]:
        depended_on = {dep for node in self for dep in node.dependencies}
        return [node for node in self if node.id not in depended_on]

    def validate(self) -> None:
        """Validate that all dependencies exist and that the graph is acyclic."""

        missing = {
            dependency
            for node in self
            for dependency in node.dependencies
            if dependency not in self._nodes
        }
        if missing:
            raise ValueError(f"missing task dependencies: {sorted(missing)}")
        self.topological_sort()

    def topological_sort(self) -> list[TaskNode]:
        """Return nodes in dependency-safe order or raise on cycles."""

        incoming = {node.id: len(node.dependencies) for node in self}
        outgoing: dict[str, set[str]] = {node.id: set() for node in self}
        for node in self:
            for dependency in node.dependencies:
                outgoing[dependency].add(node.id)

        ready = deque(sorted(node_id for node_id, count in incoming.items() if count == 0))
        ordered: list[TaskNode] = []
        while ready:
            node_id = ready.popleft()
            ordered.append(self.get(node_id))
            for dependent_id in sorted(outgoing[node_id]):
                incoming[dependent_id] -= 1
                if incoming[dependent_id] == 0:
                    ready.append(dependent_id)

        if len(ordered) != len(self._nodes):
            cycle_nodes = sorted(node_id for node_id, count in incoming.items() if count > 0)
            raise ValueError(f"task graph contains a cycle involving: {cycle_nodes}")
        return ordered

    def traversal_layers(self) -> list[list[TaskNode]]:
        """Group nodes into layers that can be executed in parallel."""

        remaining = set(self._nodes)
        completed: set[str] = set()
        layers: list[list[TaskNode]] = []
        while remaining:
            layer_ids = sorted(
                node_id
                for node_id in remaining
                if self.get(node_id).dependencies <= completed
            )
            if not layer_ids:
                raise ValueError("task graph cannot be layered; validate for cycles first")
            layers.append([self.get(node_id) for node_id in layer_ids])
            completed.update(layer_ids)
            remaining.difference_update(layer_ids)
        return layers
