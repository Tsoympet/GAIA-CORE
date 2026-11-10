"""Tool catalog status. This route does not execute tools."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/tools", tags=["tools"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/status", response_model=CommandResponse)
async def tool_status(services: ServicesDep) -> CommandResponse:
    status = services.tools.status(services.permissions)
    return CommandResponse(detail="tool catalog ready", data=status)
