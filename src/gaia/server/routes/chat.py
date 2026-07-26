"""Chat route module."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    services: ServicesDep,
) -> ChatResponse:
    reply = await services.model_router.generate(
        request.message,
        capability="chat",
        model_id=request.model_id,
    )
    return ChatResponse(
        message=reply,
        session_id=request.session_id or str(uuid4()),
    )
