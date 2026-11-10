"""Explicit idle-cognition cycles. These do not act on the outside world."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gaia.cognition import note_strings
from gaia.server.deps import GaiaServices, get_services
from gaia.server.routes.dreaming import DreamCycleRequest
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/idle-cognition", tags=["idle-cognition"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/status", response_model=CommandResponse)
async def idle_status(services: ServicesDep) -> CommandResponse:
    stored = services.cognition.latest("idle")
    notes: list[str]
    if stored is not None:
        notes = note_strings(stored.payload)
    elif services.last_idle is not None:
        notes = list(services.last_idle.notes)
    else:
        notes = []
    return CommandResponse(
        detail="idle cognition ready",
        data={
            "can_run_cycle": services.idle_scheduler.can_run_cycle(),
            "external_actions": False,
            "last_notes": notes,
            "records": len(services.idle_memory.records),
            "durable": True,
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
    services.cognition.append(
        "idle",
        "\n".join(report.notes),
        {"notes": report.notes, "external_actions": False},
    )
    return CommandResponse(
        detail="idle cognition cycle completed",
        data={
            "notes": report.notes,
            "external_actions": False,
            "records": len(services.idle_memory.records),
        },
    )
