"""Security route module."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/security", tags=["security"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/status")
async def security_status(services: ServicesDep) -> dict[str, Any]:
    """Return the state used by permission checks and API controls."""
    return {
        "status": "ok",
        "sandbox_required": services.security_policy.sandbox_required,
        "human_override_available": (
            services.security_policy.human_override_available
        ),
        "autonomy_kill_switch": services.kill_switch.enabled,
        "kill_switch_reason": services.kill_switch.reason,
        "risky_actions_require_permission": True,
    }


@router.post("/kill-switch", response_model=CommandResponse)
async def trigger_kill_switch(
    reason: str,
    services: ServicesDep,
) -> CommandResponse:
    services.permissions.activate_kill_switch(reason)
    return CommandResponse(
        detail="autonomy kill switch triggered",
        data={"reason": reason},
    )


@router.delete("/kill-switch", response_model=CommandResponse)
async def reset_kill_switch(
    services: ServicesDep,
) -> CommandResponse:
    services.permissions.deactivate_kill_switch()
    return CommandResponse(detail="autonomy kill switch reset")
