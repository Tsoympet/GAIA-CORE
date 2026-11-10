"""Simulated self-model status derived from the live runtime."""

from __future__ import annotations

from fastapi import APIRouter, Request

from gaia.core.runtime import GaiaRuntime
from gaia.self_model import build_runtime_self_model
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/self-model", tags=["self-model"])


def _capabilities(request: Request) -> list[tuple[str, str]]:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, GaiaRuntime):
        return []
    return [
        (capability.name, capability.description)
        for capability in runtime.capability_router.list_capabilities()
    ]


@router.get("/status", response_model=CommandResponse)
async def self_model_status(request: Request) -> CommandResponse:
    snapshot = build_runtime_self_model(_capabilities(request)).snapshot()
    return CommandResponse(
        detail="simulated self-model ready",
        data=snapshot.model_dump(mode="json"),
    )
