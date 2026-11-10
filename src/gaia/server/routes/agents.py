"""Live agent registry status."""

from __future__ import annotations

from fastapi import APIRouter, Request

from gaia.core.runtime import GaiaRuntime
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/agents", tags=["agents"])


def _runtime(request: Request) -> GaiaRuntime | None:
    runtime = getattr(request.app.state, "runtime", None)
    if isinstance(runtime, GaiaRuntime):
        return runtime
    return None


@router.get("/status", response_model=CommandResponse)
async def agent_status(request: Request) -> CommandResponse:
    runtime = _runtime(request)
    if runtime is None:
        return CommandResponse(
            detail="agent registry unavailable",
            data={"agents": [], "count": 0},
        )
    agents = [
        descriptor.model_dump(mode="json")
        for descriptor in runtime.agent_registry.list_descriptors()
    ]
    return CommandResponse(
        detail="agent registry ready",
        data={"agents": agents, "count": len(agents)},
    )
