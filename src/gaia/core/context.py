"""Execution context objects shared across runtime components."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from gaia.core.session import Session

MemoryHook = Callable[[str, dict[str, Any]], Awaitable[Any] | Any]


@dataclass(slots=True)
class SecurityContext:
    """Capability-oriented security information for an execution."""

    principal: str = "anonymous"
    roles: set[str] = field(default_factory=set)
    capabilities: set[str] = field(default_factory=set)
    policy: dict[str, Any] = field(default_factory=dict)

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities or "*" in self.capabilities


@dataclass(slots=True)
class ExecutionContext:
    """Immutable-ish context passed into agents, orchestrators, and hooks."""

    session: Session
    workspace: Path
    config: dict[str, Any]
    security: SecurityContext = field(default_factory=SecurityContext)
    memory_hooks: list[MemoryHook] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))

    def child(
        self,
        *,
        session: Session | None = None,
        workspace: Path | None = None,
        config: dict[str, Any] | None = None,
        security: SecurityContext | None = None,
        memory_hooks: list[MemoryHook] | None = None,
        trace_id: str | None = None,
    ) -> ExecutionContext:
        """Create a typed derived context while preserving traceability."""
        return ExecutionContext(
            session=self.session if session is None else session,
            workspace=self.workspace if workspace is None else workspace,
            config=dict(self.config if config is None else config),
            security=self.security if security is None else security,
            memory_hooks=list(
                self.memory_hooks if memory_hooks is None else memory_hooks
            ),
            trace_id=self.trace_id if trace_id is None else trace_id,
        )

    async def emit_memory_hook(
        self,
        name: str,
        payload: dict[str, Any],
    ) -> list[Any]:
        """Invoke configured memory hooks in order and return their results."""
        results: list[Any] = []
        for hook in self.memory_hooks:
            result = hook(name, payload)
            if hasattr(result, "__await__"):
                result = await result
            results.append(result)
        return results
