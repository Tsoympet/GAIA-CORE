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

from gaia.continuity.errors import ContinuityIntegrityError
from gaia.continuity.journal import ContinuityJournal
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


class ApprovalDecisionRequest(BaseModel):
    """Operator decision for a waiting continuity task."""

    decision: str
    approver: str = "operator"
    reason: str = "operator denied the requested action"


class RollbackRequest(BaseModel):
    """Restore live continuity state from a published checkpoint."""

    checkpoint_id: str


class BranchRequest(BaseModel):
    """Fork a verified checkpoint into a recorded work branch."""

    parent_checkpoint_id: str
    reason: str
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    tool_policy: dict[str, Any] = Field(default_factory=dict)


class DeleteGoalRequest(BaseModel):
    """Delete live continuity state for one goal."""

    reason: str = "operator deletion"


def _unavailable() -> dict[str, object]:
    return {
        "capability": "cognitive_continuity",
        "status": "unavailable",
        "durable": False,
        "reason": "Continuity store is not configured for this runtime.",
    }


def _journal(request: Request) -> ContinuityJournal:
    runtime = _runtime(request)
    journal = runtime.kernel.continuity
    if journal is None:
        raise HTTPException(status_code=409, detail=_unavailable())
    return journal


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
    runtime.persist_session(session)
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


@router.get("/continuity")
async def continuity_status(request: Request) -> dict[str, object]:
    """Report cognitive continuity capability and journal integrity."""
    runtime = _runtime(request)
    if runtime.kernel.continuity is None:
        return _unavailable()
    return runtime.kernel.continuity.status_summary()


@router.get("/continuity/events/stream")
async def stream_continuity_events(
    request: Request,
    once: bool = False,
) -> StreamingResponse:
    """Stream live continuity events as Server-Sent Events.

    When no journal is configured, emit an unavailable snapshot and close.
    When ``once`` is true, emit the current snapshot and close. Live events
    are process-local. They are not a second durable ledger.
    """
    runtime = _runtime(request)
    journal = runtime.kernel.continuity

    async def event_generator() -> AsyncIterator[str]:
        if journal is None:
            yield (
                "event: snapshot\n"
                f"data: {json.dumps({**_unavailable(), 'events': []}, default=str)}\n\n"
            )
            return
        snapshot = [event.model_dump(mode="json") for event in journal.recent_events()]
        snapshot_body = {
            "status": journal.capability_status(),
            "events": snapshot,
            "cryptographic_immutability": False,
        }
        yield f"event: snapshot\ndata: {json.dumps(snapshot_body, default=str)}\n\n"
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

        token = await runtime.event_bus.subscribe(EventDomain.CONTINUITY, enqueue)
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
                    "cryptographic_immutability": False,
                }
                yield f"event: continuity\ndata: {json.dumps(payload, default=str)}\n\n"
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


@router.get("/continuity/snapshots")
async def continuity_snapshots(
    request: Request,
    checkpoint_id: str | None = None,
) -> dict[str, object]:
    """Return repository and process observations for one checkpoint.

    Observations do not modify the worktree, resume a process, or switch models.
    """
    journal = _journal(request)
    try:
        return journal.environment_report(checkpoint_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/continuity/checkpoints")
async def list_checkpoints(request: Request) -> dict[str, object]:
    """List published continuity checkpoints without payload bodies."""
    journal = _journal(request)
    checkpoints = journal.store.list_checkpoints()
    return {
        "checkpoints": [item.model_dump(mode="json") for item in checkpoints],
        "count": len(checkpoints),
        "integrity_ok": journal.store.verify_chain(),
    }


@router.post("/continuity/checkpoints")
async def publish_checkpoint(request: Request) -> dict[str, object]:
    """Publish a verified snapshot of the current journal."""
    runtime = _runtime(request)
    journal = _journal(request)
    checkpoint = journal.publish(reason="operator", kernel_id=runtime.kernel.state.kernel_id)
    return {"checkpoint": checkpoint.model_dump(mode="json")}


@router.get("/continuity/checkpoints/{checkpoint_id}")
async def get_checkpoint(checkpoint_id: str, request: Request) -> dict[str, object]:
    """Return one checkpoint, including its payload."""
    journal = _journal(request)
    checkpoint = journal.store.get_checkpoint(checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail=f"unknown checkpoint: {checkpoint_id}")
    return {
        "checkpoint": checkpoint.model_dump(mode="json"),
        "verified": journal.store.verify_checkpoint(checkpoint_id),
    }


@router.post("/continuity/checkpoints/{checkpoint_id}/verify")
async def verify_checkpoint(checkpoint_id: str, request: Request) -> dict[str, object]:
    """Verify one checkpoint payload and the published hash chain."""
    journal = _journal(request)
    return {
        "checkpoint_id": checkpoint_id,
        "verified": journal.store.verify_checkpoint(checkpoint_id),
        "chain_ok": journal.store.verify_chain(),
        "cryptographic_immutability": False,
    }


@router.post("/continuity/rollback")
async def rollback_checkpoint(body: RollbackRequest, request: Request) -> dict[str, object]:
    """Restore live state from a verified checkpoint."""
    runtime = _runtime(request)
    journal = _journal(request)
    try:
        checkpoint = journal.rollback(
            body.checkpoint_id,
            kernel_id=runtime.kernel.state.kernel_id,
        )
    except ContinuityIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    journal.hydrate(runtime.kernel.goals, runtime.kernel.contexts, replace=True)
    runtime.kernel.mirror_live_state(drop_missing=True)
    return {"checkpoint": checkpoint.model_dump(mode="json")}


@router.get("/continuity/tasks")
async def list_task_runs(request: Request) -> dict[str, object]:
    """List persistent task-state records."""
    journal = _journal(request)
    tasks = journal.store.list_tasks()
    return {
        "tasks": [task.model_dump(mode="json") for task in tasks],
        "count": len(tasks),
    }


@router.post("/continuity/tasks/{goal_id}/resume")
async def resume_task(goal_id: str, request: Request) -> dict[str, object]:
    """Resume an interrupted task or a waiting task with a live approval."""
    runtime = _runtime(request)
    _journal(request)
    try:
        result = await runtime.kernel.resume(goal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"result": result.model_dump(mode="json")}


@router.post("/continuity/tasks/{goal_id}/approval")
async def decide_approval(
    goal_id: str,
    body: ApprovalDecisionRequest,
    request: Request,
) -> dict[str, object]:
    """Approve or deny a waiting task.

    Approval is bound to the current process and action fingerprint.
    It is not a reusable token and does not survive recovery.
    """
    runtime = _runtime(request)
    _journal(request)
    decision = body.decision.strip().lower()
    try:
        if decision == "approve":
            goal = runtime.kernel.grant_approval(goal_id, body.approver)
            detail = "process-local approval recorded; it is not reusable after recovery"
        elif decision == "deny":
            goal = runtime.kernel.deny_approval(goal_id, body.approver, body.reason)
            detail = "approval denied"
        else:
            raise HTTPException(status_code=400, detail="decision must be approve or deny")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"detail": detail, "goal": goal.model_dump(mode="json"), "reusable": False}


@router.post("/continuity/branches")
async def create_branch(body: BranchRequest, request: Request) -> dict[str, object]:
    """Record a work branch at a verified checkpoint."""
    runtime = _runtime(request)
    journal = _journal(request)
    model_configuration = body.model_configuration or {
        "local_first": runtime.model_catalog.local_first,
        "providers": [
            provider.model_dump(mode="json") for provider in runtime.model_catalog.providers
        ],
    }
    tool_policy = body.tool_policy or {
        "sandbox_required": runtime.security_policy.sandbox_required,
        "human_override_available": runtime.security_policy.human_override_available,
        "blocked_terms": list(runtime.security_policy.blocked_terms),
    }
    try:
        branch = journal.store.create_branch(
            body.parent_checkpoint_id,
            body.reason,
            model_configuration,
            tool_policy,
        )
    except ContinuityIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"branch": branch.model_dump(mode="json")}


@router.get("/continuity/branches")
async def list_branches(request: Request) -> dict[str, object]:
    """List recorded work branches."""
    journal = _journal(request)
    branches = journal.store.list_branches()
    return {
        "branches": [branch.model_dump(mode="json") for branch in branches],
        "count": len(branches),
    }


@router.post("/continuity/branches/{branch_id}/materialize")
async def materialize_branch(branch_id: str, request: Request) -> dict[str, object]:
    """Restore the branch parent checkpoint into the live journal."""
    runtime = _runtime(request)
    journal = _journal(request)
    branch = journal.store.get_branch(branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"unknown branch: {branch_id}")
    try:
        checkpoint = journal.store.rollback_to(
            branch.parent_checkpoint_id,
            kernel_id=runtime.kernel.state.kernel_id,
        )
    except ContinuityIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    journal.hydrate(runtime.kernel.goals, runtime.kernel.contexts, replace=True)
    runtime.kernel.mirror_live_state(drop_missing=True)
    return {
        "branch": branch.model_dump(mode="json"),
        "checkpoint": checkpoint.model_dump(mode="json"),
    }


@router.get("/continuity/audit")
async def export_audit(request: Request) -> dict[str, object]:
    """Export a continuity audit bundle."""
    journal = _journal(request)
    return journal.store.export_audit_bundle()


@router.post("/continuity/goals/{goal_id}/delete")
async def delete_goal_state(
    goal_id: str,
    request: Request,
    body: DeleteGoalRequest | None = None,
) -> dict[str, object]:
    """Delete live continuity rows for a goal.

    Published checkpoints are retained and are not rewritten.
    """
    runtime = _runtime(request)
    journal = _journal(request)
    reason = body.reason if body is not None else "operator deletion"
    deleted = journal.store.delete_goal(goal_id, reason)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"unknown goal: {goal_id}")
    runtime.kernel.store.delete_goal(goal_id)
    runtime.kernel.goals.discard(goal_id)
    runtime.kernel.contexts.release(goal_id)
    runtime.kernel._budgets.pop(goal_id, None)
    return {
        "deleted": True,
        "live_state_removed": True,
        "published_checkpoints_retained": True,
        "goal_id": goal_id,
    }
