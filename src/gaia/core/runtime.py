"""Async runtime state machine for GAIA Core."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .context import ExecutionContext
from .event_bus import Event, EventBus, EventDomain
from .lifecycle import HealthStatus, LifecycleManager

TaskCallable = Callable[[Any, ExecutionContext], Awaitable[Any] | Any]


class RuntimeStatus(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class TaskRecord:
    """Runtime-visible state for a submitted task."""

    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    trace_id: str | None = None
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None


class JsonFormatter(logging.Formatter):
    """Minimal structured log formatter for runtime logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("task_id", "trace_id", "status"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, default=str)


class GaiaRuntime:
    """Coordinates lifecycle, task execution, cancellation, and observability."""

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        lifecycle: LifecycleManager | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.event_bus = event_bus or EventBus()
        self.lifecycle = lifecycle or LifecycleManager()
        self.logger = logger or logging.getLogger("gaia.runtime")
        self.status = RuntimeStatus.CREATED
        self._tasks: dict[str, TaskRecord] = {}
        self._asyncio_tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Transition the runtime into the running state."""

        if self.status == RuntimeStatus.RUNNING:
            return
        if self.status == RuntimeStatus.STOPPING:
            raise RuntimeError("runtime is stopping")
        self.status = RuntimeStatus.STARTING
        await self._publish_runtime("starting")
        try:
            await self.lifecycle.startup()
        except Exception:
            self.status = RuntimeStatus.FAILED
            await self._publish_runtime("failed")
            raise
        self.status = RuntimeStatus.RUNNING
        await self._publish_runtime("started")
        self.logger.info("runtime started", extra={"status": self.status.value})

    async def shutdown(self, *, cancel_pending: bool = True) -> None:
        """Stop the runtime and optionally cancel in-flight tasks."""

        if self.status in {RuntimeStatus.STOPPED, RuntimeStatus.CREATED}:
            self.status = RuntimeStatus.STOPPED
            self.lifecycle.health.set(HealthStatus.STOPPED)
            await self.event_bus.close()
            return
        self.status = RuntimeStatus.STOPPING
        await self._publish_runtime("stopping")
        if cancel_pending:
            await self.cancel_all()
        pending = list(self._asyncio_tasks.values())
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        try:
            await self.lifecycle.shutdown()
        finally:
            self.status = RuntimeStatus.STOPPED
            await self._publish_runtime("stopped")
            await self.event_bus.close()
            self.logger.info("runtime stopped", extra={"status": self.status.value})

    async def submit(
        self,
        name: str,
        handler: TaskCallable,
        payload: Any,
        context: ExecutionContext,
    ) -> TaskRecord:
        """Submit a task for asynchronous execution."""

        if self.status != RuntimeStatus.RUNNING:
            raise RuntimeError(f"runtime is not running: {self.status.value}")
        task_id = str(uuid4())
        record = TaskRecord(task_id=task_id, name=name, trace_id=context.trace_id)
        async with self._lock:
            self._tasks[task_id] = record
            self._asyncio_tasks[task_id] = asyncio.create_task(
                self._run_task(record, handler, payload, context),
                name=f"gaia-task-{task_id}",
            )
        await self._publish_task("submitted", record)
        return record

    async def wait_for_task(self, task_id: str) -> TaskRecord:
        """Wait for a submitted task to reach a terminal state."""

        task = self._asyncio_tasks.get(task_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        return await self.require_task(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task by id."""

        task = self._asyncio_tasks.get(task_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def cancel_all(self) -> None:
        """Cancel all currently running asyncio tasks."""

        for task in self._asyncio_tasks.values():
            if not task.done():
                task.cancel()

    async def get_task(self, task_id: str) -> TaskRecord | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def require_task(self, task_id: str) -> TaskRecord:
        record = await self.get_task(task_id)
        if record is None:
            raise KeyError(f"task not found: {task_id}")
        return record

    async def list_tasks(self) -> list[TaskRecord]:
        async with self._lock:
            return list(self._tasks.values())

    async def _run_task(
        self,
        record: TaskRecord,
        handler: TaskCallable,
        payload: Any,
        context: ExecutionContext,
    ) -> None:
        record.status = TaskStatus.RUNNING
        record.started_at = datetime.now(UTC)
        await self._publish_task("started", record)
        self.logger.info(
            "task started",
            extra={"task_id": record.task_id, "trace_id": record.trace_id, "status": record.status.value},
        )
        try:
            result = handler(payload, context)
            if hasattr(result, "__await__"):
                result = await result
            record.result = result
            record.status = TaskStatus.SUCCEEDED
            await self._publish_task("succeeded", record)
        except asyncio.CancelledError:
            record.status = TaskStatus.CANCELLED
            record.error = "cancelled"
            await self._publish_task("cancelled", record)
            raise
        except Exception as exc:
            record.status = TaskStatus.FAILED
            record.error = str(exc)
            await self._publish_task("failed", record)
            self.logger.exception(
                "task failed",
                extra={"task_id": record.task_id, "trace_id": record.trace_id, "status": record.status.value},
            )
        finally:
            record.completed_at = datetime.now(UTC)
            async with self._lock:
                self._asyncio_tasks.pop(record.task_id, None)
            self.logger.info(
                "task completed",
                extra={"task_id": record.task_id, "trace_id": record.trace_id, "status": record.status.value},
            )

    async def _publish_task(self, name: str, record: TaskRecord) -> None:
        await self.event_bus.publish(
            Event(
                domain=EventDomain.TASK,
                name=name,
                trace_id=record.trace_id,
                payload=asdict(record),
            )
        )

    async def _publish_runtime(self, name: str) -> None:
        await self.event_bus.publish(
            Event(
                domain=EventDomain.RUNTIME,
                name=name,
                payload={"status": self.status.value},
            )
        )
