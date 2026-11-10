"""Chat route module."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    services: ServicesDep,
) -> ChatResponse:
    try:
        reply = await services.model_router.complete(
            request.message,
            capability="chat",
            model_id=request.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatResponse(
        message=reply.text,
        session_id=request.session_id or str(uuid4()),
        model_id=reply.model_id,
        provider=reply.provider,
        local_fallback=reply.local_fallback,
        deterministic=reply.deterministic,
    )
