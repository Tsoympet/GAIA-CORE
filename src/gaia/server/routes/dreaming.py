"""Idle dreaming that cannot take external actions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gaia.cognition import note_strings
from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse, GaiaSchema

router = APIRouter(prefix="/dreaming", tags=["dreaming"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


class DreamCycleRequest(GaiaSchema):
    """Optional seeds for an internal-only idle cycle."""

    failed_task: str | None = None
    future_goal: str | None = None


@router.get("/status", response_model=CommandResponse)
async def dreaming_status(services: ServicesDep) -> CommandResponse:
    guard = services.dream_engine.guard
    return CommandResponse(
        detail="dream laboratory is idle-only",
        data={
            "external_actions": False,
            "can_simulate": guard.check("simulate").allowed,
            "blocks_shell": not guard.check("shell.command").allowed,
            "last_notes": _dream_notes(services),
            "records": len(services.dream_memory.records),
            "durable": True,
            "journal": services.cognition.status(),
        },
    )


@router.post("/cycle", response_model=CommandResponse)
async def dreaming_cycle(
    services: ServicesDep,
    request: DreamCycleRequest | None = None,
) -> CommandResponse:
    payload = request or DreamCycleRequest()
    report = await services.dream_engine.run_idle_cycle(
        services.dream_memory,
        failed_task=payload.failed_task,
        future_goal=payload.future_goal,
    )
    services.last_dream = report
    services.cognition.append(
        "dream",
        "\n".join(report.notes),
        {"notes": report.notes, "external_actions": False},
    )
    return CommandResponse(
        detail="idle cognition cycle completed",
        data={
            "notes": report.notes,
            "external_actions": False,
            "records": len(services.dream_memory.records),
            "durable": True,
        },
    )


def _dream_notes(services: GaiaServices) -> list[str]:
    """Prefer the SQLite journal so a new process still sees the last cycle."""
    stored = services.cognition.latest("dream")
    if stored is not None:
        return note_strings(stored.payload)
    if services.last_dream is not None:
        return list(services.last_dream.notes)
    return []
