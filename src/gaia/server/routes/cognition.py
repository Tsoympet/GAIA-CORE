"""Read the local phase-4, dream, and metacognition journal."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from gaia.cognition import NOTE_KINDS
from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse

router = APIRouter(prefix="/cognition", tags=["cognition"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/notes", response_model=CommandResponse)
async def list_cognition_notes(
    services: ServicesDep,
    kind: Annotated[str | None, Query()] = None,
    owner_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> CommandResponse:
    """List journal notes. Owner filters hide rows that belong to someone else.

    Dream and metacognition notes have no owner, so an owner filter does not
    return them. This route does not run a tool or an external action.
    """
    if kind is not None and kind not in NOTE_KINDS:
        raise HTTPException(status_code=400, detail="unsupported cognition note kind")
    try:
        notes = services.cognition.list_notes(kind, owner_id=owner_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CommandResponse(
        detail="cognition journal",
        data={
            "external_actions": False,
            "durable": True,
            "notes": [
                {
                    "note_id": note.note_id,
                    "kind": note.kind,
                    "body": note.body,
                    "payload": note.payload,
                    "created_at": note.created_at.isoformat(),
                }
                for note in notes
            ],
        },
    )
