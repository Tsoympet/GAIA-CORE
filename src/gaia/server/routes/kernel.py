"""Cognitive Kernel operator API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gaia.core.event_bus import Event, EventDomain
from gaia.core.runtime import GaiaRuntime
from gaia.kernel.goal_manager import GoalStatus
from gaia.kernel.resource_budget import ResourceBudget
from gaia.security.permission_manager import Permission

router = APIRouter(prefix="/kernel", tags=["kernel"])


class CancelGoalRequest(BaseModel):
    """Request body for cancelling a kernel goal."""

    reason: str = "operator cancel"


class ResumeGoalRequest(BaseModel):
    """Optional overrides when resuming an interrupted goal."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    budget: ResourceBudget | None = None


class KernelTaskRequest(BaseModel):
    """Submit a task through the Cognitive Kernel control plane."""

    task: str
    session_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    budget: ResourceBudget | None = None


class BackupRequest(BaseModel):
    """Request body for creating a kernel backup."""

    destination: str = ".gaia/backups/kernel-backup"


class RestoreRequest(BaseModel):
    """Request body for restoring a kernel backup."""

    source: str


def _runtime(request: Request) -> GaiaRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, GaiaRuntime) or runtime.kernel is None:
        raise HTTPException(status_code=503, detail="Cognitive Kernel is unavailable")
    return runtime


def _require_permission(
    runtime: GaiaRuntime,
    permission: Permission,
    resource: str = "*",
    *,
    actor: str = "kernel-api",
) -> None:
    decision = runtime.permission_manager.check(permission, resource, actor=actor)
    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "permission denied",
                "permission": permission.value,
                "reason": decision.reason,
                "requires_human_approval": decision.requires_human_approval,
            },
        )


@router.get("/status")
async def kernel_status(request: Request) -> dict[str, object]:
    """Return Cognitive Kernel status and counters."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    state = runtime.kernel.status()
    return {
        "status": "ok",
        "kernel": state.model_dump(mode="json"),
        "active_contexts": runtime.kernel.contexts.active_count(),
        "pending_interrupts": runtime.kernel.interrupts.pending_count(),
        "persistence": runtime.kernel.store.status(),
        "config": runtime.kernel_config.model_dump(mode="json"),
    }


@router.get("/goals")
async def list_goals(
    request: Request,
    session_id: str | None = None,
    status: GoalStatus | None = None,
) -> dict[str, object]:
    """List kernel-tracked goals."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    goals = runtime.kernel.goals.list_goals(session_id=session_id, status=status)
    return {
        "goals": [goal.model_dump(mode="json") for goal in goals],
        "count": len(goals),
    }


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str, request: Request) -> dict[str, object]:
    """Return one goal with context and budget snapshots."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    goal = runtime.kernel.goals.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"unknown goal: {goal_id}")
    interrupt = runtime.kernel.interrupts.get(goal_id)
    return {
        "goal": goal.model_dump(mode="json"),
        "context": runtime.kernel.contexts.snapshot(goal_id),
        "budget": runtime.kernel.get_budget(goal_id),
        "interrupt": interrupt.model_dump(mode="json") if interrupt is not None else None,
        "events": [
            event.model_dump(mode="json")
            for event in runtime.kernel.events.list_events(goal_id=goal_id, limit=50)
        ],
    }


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, request: Request) -> dict[str, object]:
    """Delete a goal and all durable derivatives."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_DELETE, goal_id)
    if runtime.kernel.goals.get(goal_id) is None and runtime.kernel.store.get_goal(goal_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown goal: {goal_id}")
    removed = runtime.kernel.delete_goal(goal_id)
    await runtime.kernel.events.emit(
        "goal.deleted",
        goal_id=goal_id,
        payload={"removed": removed},
    )
    return {"detail": "goal deleted", "goal_id": goal_id, "removed": removed}


@router.post("/goals/{goal_id}/cancel")
async def cancel_goal(
    goal_id: str,
    request: Request,
    body: CancelGoalRequest | None = None,
) -> dict[str, object]:
    """Cancel or interrupt a kernel-managed goal."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    reason = body.reason if body is not None else "operator cancel"
    try:
        goal = runtime.kernel.cancel_goal(goal_id, reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "detail": "goal cancel requested",
        "goal": goal.model_dump(mode="json"),
        "pending_interrupt": runtime.kernel.interrupts.is_interrupted(goal_id),
    }


@router.post("/goals/{goal_id}/resume")
async def resume_goal(
    goal_id: str,
    request: Request,
    body: ResumeGoalRequest | None = None,
) -> dict[str, object]:
    """Resume an interrupted goal through another verified kernel run."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    metadata = body.metadata if body is not None else {}
    budget = body.budget if body is not None else None
    try:
        result = await runtime.kernel.resume(
            goal_id,
            budget=budget,
            metadata=metadata,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="GAIA kernel resume failed",
        ) from exc
    return {
        "runtime_id": runtime.runtime_id,
        "result": result.model_dump(mode="json"),
    }


@router.get("/interrupts")
async def interrupt_history(request: Request) -> dict[str, object]:
    """Return interrupt history for operator audit."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    history = runtime.kernel.interrupts.history()
    return {
        "interrupts": [item.model_dump(mode="json") for item in history],
        "pending": runtime.kernel.interrupts.pending_count(),
    }


@router.get("/events")
async def list_kernel_events(
    request: Request,
    goal_id: str | None = None,
    after_id: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> dict[str, object]:
    """List durable kernel lifecycle events."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    events = runtime.kernel.events.list_events(
        goal_id=goal_id,
        after_id=after_id,
        since=since,
        limit=limit,
    )
    return {
        "events": [event.model_dump(mode="json") for event in events],
        "count": len(events),
        "persistence": runtime.kernel.store.status(),
    }


@router.get("/events/stream")
async def stream_kernel_events(
    request: Request,
    once: bool = False,
) -> StreamingResponse:
    """Stream kernel lifecycle events as Server-Sent Events.

    When ``once`` is true, emit the current snapshot and close. This supports
    deterministic tests and lightweight polling clients.
    """
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)

    async def event_generator() -> AsyncIterator[str]:
        snapshot = [
            event.model_dump(mode="json")
            for event in runtime.kernel.events.recent()
        ]
        yield (
            "event: snapshot\n"
            f"data: {json.dumps({'events': snapshot}, default=str)}\n\n"
        )
        if once:
            return

        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)

        async def enqueue(event: Event) -> None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(event)

        token = await runtime.event_bus.subscribe(EventDomain.KERNEL, enqueue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                payload = {
                    "event_id": event.event_id,
                    "domain": event.domain.value,
                    "name": event.name,
                    "payload": event.payload,
                    "trace_id": event.trace_id,
                    "timestamp": event.timestamp.isoformat(),
                }
                yield f"event: kernel\ndata: {json.dumps(payload, default=str)}\n\n"
        finally:
            await runtime.event_bus.unsubscribe(token)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/backup")
async def backup_kernel(body: BackupRequest, request: Request) -> dict[str, object]:
    """Create a portable backup of durable kernel state."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_BACKUP)
    path = runtime.kernel.backup(body.destination)
    await runtime.kernel.events.emit(
        "kernel.backup_created",
        payload={"destination": str(path)},
    )
    return {
        "detail": "kernel backup created",
        "destination": str(path),
        "persistence": runtime.kernel.store.status(),
    }


@router.post("/restore")
async def restore_kernel(body: RestoreRequest, request: Request) -> dict[str, object]:
    """Restore durable kernel state from a backup."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_ADMIN)
    try:
        runtime.kernel.restore(body.source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await runtime.kernel.events.emit(
        "kernel.restored",
        payload={"source": body.source},
    )
    return {
        "detail": "kernel state restored",
        "source": body.source,
        "goals": runtime.kernel.goals.count(),
        "persistence": runtime.kernel.store.status(),
    }


@router.post("/purge")
async def purge_kernel(request: Request) -> dict[str, object]:
    """Purge all durable and live kernel state."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_ADMIN)
    counts = runtime.kernel.purge()
    await runtime.kernel.events.emit("kernel.purged", payload=counts)
    return {"detail": "kernel purged", "removed": counts}


@router.post("/tasks")
async def submit_kernel_task(
    body: KernelTaskRequest,
    request: Request,
) -> dict[str, object]:
    """Run a task through the Cognitive Kernel (goal + budget + verification)."""
    runtime = _runtime(request)
    _require_permission(runtime, Permission.KERNEL_READ)
    session = await runtime.sessions.get_or_create(body.session_id)
    try:
        result = await runtime.kernel.run(
            body.task,
            session.id,
            body.capabilities,
            budget=body.budget,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="GAIA kernel task execution failed",
        ) from exc
    return {
        "runtime_id": runtime.runtime_id,
        "result": result.model_dump(mode="json"),
    }
