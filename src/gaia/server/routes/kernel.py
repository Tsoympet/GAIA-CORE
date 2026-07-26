"""Cognitive Kernel operator routes."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gaia.core.runtime import GaiaRuntime
from gaia.kernel import (
    CognitiveKernel,
    GoalRecord,
    KernelExecution,
    KernelStatus,
)

router = APIRouter(prefix="/kernel", tags=["kernel"])


class GoalCreateRequest(BaseModel):
    """Create a kernel-managed goal."""

    objective: str = Field(min_length=1)
    priority: int = Field(default=50, ge=0, le=100)
    parent_goal_id: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CancellationRequest(BaseModel):
    """Request cooperative cancellation of an execution."""

    reason: str = Field(min_length=1)


def _kernel(request: Request) -> CognitiveKernel:
    runtime = cast(GaiaRuntime, request.app.state.runtime)
    return runtime.kernel


@router.get("/status", response_model=KernelStatus)
async def kernel_status(request: Request) -> KernelStatus:
    return _kernel(request).status()


@router.get("/goals", response_model=list[GoalRecord])
async def list_goals(request: Request) -> list[GoalRecord]:
    return _kernel(request).goals.list()


@router.post("/goals", response_model=GoalRecord)
async def create_goal(
    request_body: GoalCreateRequest,
    request: Request,
) -> GoalRecord:
    try:
        return _kernel(request).goals.create(
            request_body.objective,
            priority=request_body.priority,
            parent_goal_id=request_body.parent_goal_id,
            project_id=request_body.project_id,
            metadata=request_body.metadata,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/executions", response_model=list[KernelExecution])
async def list_executions(request: Request) -> list[KernelExecution]:
    return _kernel(request).list_executions()


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    request_body: CancellationRequest,
    request: Request,
) -> dict[str, str]:
    try:
        _kernel(request).request_cancellation(
            execution_id,
            request_body.reason,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "execution_id": execution_id,
        "status": "cancellation_requested",
    }
