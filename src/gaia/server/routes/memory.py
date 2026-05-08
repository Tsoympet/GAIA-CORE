"""Memory review and scoped memory API routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gaia.memory import MemoryDeletionRequest, MemoryScope
from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import (
    CommandResponse,
    MemoryConsentRequest,
    MemoryDeletionRequestCreate,
    MemoryDeletionRequestResponse,
    MemoryDeletionReviewRequest,
    MemoryRecordResponse,
    MemoryStatusResponse,
    MemoryWriteRequest,
)

router = APIRouter(prefix="/memory", tags=["memory"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]
ScopeQuery = Annotated[
    str | None,
    Query(description="Optional memory scope: project, user, session, or timeline"),
]


@router.get("/status", response_model=MemoryStatusResponse)
async def memory_status(services: ServicesDep) -> MemoryStatusResponse:
    """Return scoped memory status for review surfaces."""
    return MemoryStatusResponse(**asdict(services.memory.status()))


@router.post("", response_model=MemoryRecordResponse)
async def remember(request: MemoryWriteRequest, services: ServicesDep) -> MemoryRecordResponse:
    """Write scoped memory when owner consent allows it."""
    try:
        record = services.memory.remember(
            request.content,
            MemoryScope(request.scope),
            request.owner_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return MemoryRecordResponse(
        record_id=record.record_id,
        scope=record.scope.value,
        owner_id=record.owner_id,
        content=record.content,
        created_at=record.created_at,
    )


@router.get("/review", response_model=list[MemoryRecordResponse])
async def review_memory(
    owner_id: str,
    services: ServicesDep,
    scope: ScopeQuery = None,
) -> list[MemoryRecordResponse]:
    """List retained records for user-facing memory review."""
    try:
        scopes = [MemoryScope(scope)] if scope else list(MemoryScope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid memory scope") from exc
    records = [
        record
        for memory_scope in scopes
        for record in services.memory.list_scope(memory_scope, owner_id)
    ]
    return [
        MemoryRecordResponse(
            record_id=record.record_id,
            scope=record.scope.value,
            owner_id=record.owner_id,
            content=record.content,
            created_at=record.created_at,
        )
        for record in records
    ]


@router.get("/export/{owner_id}")
async def export_memory(owner_id: str, services: ServicesDep) -> dict[str, Any]:
    """Export retained memory for an owner grouped by scope."""
    return {"owner_id": owner_id, "scopes": services.memory.export_owner(owner_id)}


@router.post("/consent/grant", response_model=CommandResponse)
async def grant_memory_consent(
    request: MemoryConsentRequest,
    services: ServicesDep,
) -> CommandResponse:
    """Grant future memory writes for an owner."""
    services.memory.grant_consent(request.owner_id)
    return CommandResponse(detail="memory consent granted", data={"owner_id": request.owner_id})


@router.post("/consent/revoke", response_model=CommandResponse)
async def revoke_memory_consent(
    request: MemoryConsentRequest,
    services: ServicesDep,
) -> CommandResponse:
    """Revoke future memory writes for an owner without deleting records."""
    services.memory.revoke_consent(request.owner_id)
    return CommandResponse(detail="memory consent revoked", data={"owner_id": request.owner_id})


@router.post("/deletion-requests", response_model=MemoryDeletionRequestResponse)
async def request_memory_deletion(
    request: MemoryDeletionRequestCreate,
    services: ServicesDep,
) -> MemoryDeletionRequestResponse:
    """Create a human-reviewable memory deletion request."""
    deletion_request = services.memory.request_deletion(
        request.owner_id,
        MemoryScope(request.scope),
        request.reason,
    )
    return _deletion_response(deletion_request)


@router.post(
    "/deletion-requests/{request_id}/review",
    response_model=MemoryDeletionRequestResponse,
)
async def review_memory_deletion(
    request_id: str,
    request: MemoryDeletionReviewRequest,
    services: ServicesDep,
) -> MemoryDeletionRequestResponse:
    """Approve or deny a memory deletion request."""
    try:
        deletion_request = services.memory.review_deletion_request(request_id, request.approve)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="deletion request not found") from exc
    return _deletion_response(deletion_request)


def _deletion_response(request: MemoryDeletionRequest) -> MemoryDeletionRequestResponse:
    return MemoryDeletionRequestResponse(
        request_id=request.request_id,
        owner_id=request.owner_id,
        scope=request.scope.value,
        reason=request.reason,
        status=request.status.value,
        requested_at=request.requested_at,
        reviewed_at=request.reviewed_at,
    )
