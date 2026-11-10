"""Model registry route module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gaia.models import ModelDescriptor, ModelProvider
from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse, ModelRegistrationRequest

router = APIRouter(prefix="/models", tags=["models"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


def _descriptor(model: ModelDescriptor) -> dict[str, object]:
    return {
        "model_id": model.model_id,
        "provider": model.provider.value,
        "capabilities": sorted(model.capabilities),
        "local_first": model.local_first,
        "enabled": model.enabled,
        "context_window": model.context_window,
    }


@router.get("", response_model=CommandResponse)
async def list_models(services: ServicesDep) -> CommandResponse:
    models = services.registry.list()
    health = await services.model_router.health()
    return CommandResponse(
        detail="local-first model router ready",
        data={
            "models": [model.model_id for model in models],
            "descriptors": [_descriptor(model) for model in models],
            "health": health,
        },
    )


@router.get("/health", response_model=CommandResponse)
async def model_health(services: ServicesDep) -> CommandResponse:
    return CommandResponse(
        detail="model provider health",
        data=await services.model_router.health(),
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
