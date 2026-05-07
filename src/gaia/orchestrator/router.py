"""Capability-based routing for agents, tools, and models."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .task_node import CapabilityRequirement, TaskNode


class Runnable(Protocol):
    """Callable protocol accepted by the executor."""

    def __call__(self, node: TaskNode, context: dict[str, Any]) -> Any | Awaitable[Any]:
        ...


@dataclass(frozen=True, slots=True)
class RouteTarget:
    """An executable agent, tool, or model advertised to the router."""

    id: str
    kind: str
    capabilities: frozenset[str]
    runner: Runnable
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports(self, requirement: CapabilityRequirement) -> bool:
        if requirement.preferred_kind and self.kind != requirement.preferred_kind:
            return False
        return requirement.capabilities <= self.capabilities


class CapabilityRouter:
    """Select the best route target for a task node's declared capabilities."""

    def __init__(self, targets: list[RouteTarget] | None = None) -> None:
        self._targets: dict[str, RouteTarget] = {}
        for target in targets or []:
            self.register(target)

    def register(self, target: RouteTarget) -> None:
        if target.id in self._targets:
            raise ValueError(f"duplicate route target id: {target.id}")
        self._targets[target.id] = target

    def available_targets(self) -> list[RouteTarget]:
        return sorted(self._targets.values(), key=lambda target: (-target.priority, target.id))

    def select(self, node: TaskNode) -> RouteTarget:
        matches = [target for target in self.available_targets() if target.supports(node.capability)]
        if not matches:
            required = sorted(node.capability.capabilities)
            raise LookupError(f"no route target supports task {node.id!r} capabilities: {required}")
        return matches[0]

    @classmethod
    def with_default_runner(cls, runner: Runnable) -> "CapabilityRouter":
        """Build a router that can execute tasks without explicit capabilities."""

        return cls([
            RouteTarget(
                id="default",
                kind="agent",
                capabilities=frozenset(),
                runner=runner,
            )
        ])
