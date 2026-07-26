"""Model registry route module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gaia.models import ModelDescriptor, ModelProvider
from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse, ModelRegistrationRequest

router = APIRouter(prefix="/models", tags=["models"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("", response_model=CommandResponse)
async def list_models(services: ServicesDep) -> CommandResponse:
    return CommandResponse(
        data={
            "models": [
                model.model_id
                for model in services.registry.list()
            ]
        }
    )


@router.post("", response_model=CommandResponse)
async def register_model(
    request: ModelRegistrationRequest,
    services: ServicesDep,
) -> CommandResponse:
    services.registry.register(
        ModelDescriptor(
            model_id=request.model_id,
            provider=ModelProvider(request.provider),
            capabilities=set(request.capabilities),
            context_window=request.context_window,
            enabled=request.enabled,
        )
    )
    return CommandResponse(
        detail="model registered",
        data={"model_id": request.model_id},
    )
