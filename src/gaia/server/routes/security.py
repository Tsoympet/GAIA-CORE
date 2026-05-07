"""Security route module."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/security", tags=["security"])


@router.post("/kill-switch", response_model=CommandResponse)
async def trigger_kill_switch(reason: str, services: GaiaServices = Depends(get_services)) -> CommandResponse:
    services.kill_switch.trigger(reason)
    return CommandResponse(detail="autonomy kill switch triggered", data={"reason": reason})


@router.delete("/kill-switch", response_model=CommandResponse)
async def reset_kill_switch(services: GaiaServices = Depends(get_services)) -> CommandResponse:
    services.kill_switch.reset()
    return CommandResponse(detail="autonomy kill switch reset")
