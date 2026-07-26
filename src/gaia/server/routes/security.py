"""Security route module."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/status")
async def security_status(
    services: GaiaServices = Depends(get_services),
) -> dict[str, Any]:
    """Return the state used by permission checks and API controls."""
    return {
        "status": "ok",
        "autonomy_kill_switch": services.kill_switch.enabled,
        "kill_switch_reason": services.kill_switch.reason,
        "risky_actions_require_permission": True,
    }


@router.post("/kill-switch", response_model=CommandResponse)
async def trigger_kill_switch(
    reason: str,
    services: GaiaServices = Depends(get_services),
) -> CommandResponse:
    services.permissions.activate_kill_switch(reason)
    return CommandResponse(
        detail="autonomy kill switch triggered",
        data={"reason": reason},
    )


@router.delete("/kill-switch", response_model=CommandResponse)
async def reset_kill_switch(
    services: GaiaServices = Depends(get_services),
) -> CommandResponse:
    services.permissions.deactivate_kill_switch()
    return CommandResponse(detail="autonomy kill switch reset")
