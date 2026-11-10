"""Explicit idle-cognition cycles. These do not act on the outside world."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gaia.server.deps import GaiaServices, get_services
from gaia.server.routes.dreaming import DreamCycleRequest
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/idle-cognition", tags=["idle-cognition"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/status", response_model=CommandResponse)
async def idle_status(services: ServicesDep) -> CommandResponse:
    notes = list(services.last_idle.notes) if services.last_idle else []
    return CommandResponse(
        detail="idle cognition ready",
        data={
            "can_run_cycle": services.idle_scheduler.can_run_cycle(),
            "external_actions": False,
            "last_notes": notes,
            "records": len(services.idle_memory.records),
        },
    )


@router.post("/cycle", response_model=CommandResponse)
async def idle_cycle(
    services: ServicesDep,
    request: DreamCycleRequest | None = None,
) -> CommandResponse:
    if not services.idle_scheduler.can_run_cycle():
        return CommandResponse(
            accepted=False,
            detail="idle cognition refused",
            data={"external_actions": False},
        )
    payload = request or DreamCycleRequest()
    report = await services.dream_engine.run_idle_cycle(
        services.idle_memory,
        failed_task=payload.failed_task,
        future_goal=payload.future_goal,
    )
    services.last_idle = report
    return CommandResponse(
        detail="idle cognition cycle completed",
        data={
            "notes": report.notes,
            "external_actions": False,
            "records": len(services.idle_memory.records),
        },
    )
