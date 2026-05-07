"""Memory route module."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from gaia.memory import MemoryScope
from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import MemoryRecordResponse, MemoryWriteRequest

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("", response_model=MemoryRecordResponse)
async def remember(request: MemoryWriteRequest, services: GaiaServices = Depends(get_services)) -> MemoryRecordResponse:
    record = services.memory.remember(request.content, MemoryScope(request.scope), request.owner_id)
    return MemoryRecordResponse(
        record_id=record.record_id,
        scope=record.scope.value,
        owner_id=record.owner_id,
        content=record.content,
        created_at=record.created_at,
    )
