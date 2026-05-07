"""Lifecycle hook registry and health model for the GAIA runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


LifecycleHook = Callable[[], Awaitable[Any] | Any]


class HealthStatus(StrEnum):
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(slots=True)
class RuntimeHealth:
    """Current runtime health snapshot."""

    status: HealthStatus = HealthStatus.STOPPED
    details: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def set(self, status: HealthStatus, **details: Any) -> None:
        self.status = status
        self.details = details
        self.updated_at = datetime.now(UTC)


class LifecycleManager:
    """Coordinates startup and shutdown hooks."""

    def __init__(self) -> None:
        self.health = RuntimeHealth()
        self._startup_hooks: list[LifecycleHook] = []
        self._shutdown_hooks: list[LifecycleHook] = []

    def on_startup(self, hook: LifecycleHook) -> LifecycleHook:
        self._startup_hooks.append(hook)
        return hook

    def on_shutdown(self, hook: LifecycleHook) -> LifecycleHook:
        self._shutdown_hooks.append(hook)
        return hook

    async def startup(self) -> None:
        self.health.set(HealthStatus.STARTING)
        try:
            for hook in self._startup_hooks:
                await self._run_hook(hook)
        except Exception as exc:
            self.health.set(HealthStatus.FAILED, error=str(exc))
            raise
        self.health.set(HealthStatus.HEALTHY)

    async def shutdown(self) -> None:
        self.health.set(HealthStatus.STOPPING)
        errors: list[str] = []
        for hook in reversed(self._shutdown_hooks):
            try:
                await self._run_hook(hook)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            self.health.set(HealthStatus.FAILED, errors=errors)
            raise RuntimeError("shutdown hooks failed: " + "; ".join(errors))
        self.health.set(HealthStatus.STOPPED)

    async def _run_hook(self, hook: LifecycleHook) -> None:
        result = hook()
        if hasattr(result, "__await__"):
            await result
