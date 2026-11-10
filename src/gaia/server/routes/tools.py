"""Tool catalog status and the one safe local read."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse, ToolRunRequest

router = APIRouter(prefix="/tools", tags=["tools"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/status", response_model=CommandResponse)
async def tool_status(services: ServicesDep) -> CommandResponse:
    """Report permission state. This route does not execute a tool."""
    status = services.tools.status(services.permissions)
    return CommandResponse(detail="tool catalog ready", data=status)


@router.post("/run", response_model=CommandResponse)
async def run_tool(request: ToolRunRequest, services: ServicesDep) -> CommandResponse:
    """Run the local clock, or refuse every other named tool without executing it."""
    try:
        result = services.tools.run(request.name, request.text)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="tool not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return CommandResponse(detail="safe local tool completed", data=result)
