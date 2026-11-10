"""Metacognitive review over operator-supplied answers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse, GaiaSchema

router = APIRouter(prefix="/metacognition", tags=["metacognition"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


class ReviewRequest(GaiaSchema):
    """Answer text and optional confidence signals."""

    answer: str = Field(min_length=1)
    signals: dict[str, float] = Field(default_factory=dict)


@router.get("/status", response_model=CommandResponse)
async def metacognition_status(services: ServicesDep) -> CommandResponse:
    last = services.last_reflection.model_dump(mode="json") if services.last_reflection else None
    return CommandResponse(
        detail="metacognition ready",
        data={"ready": True, "external_actions": False, "last_review": last},
    )


@router.post("/review", response_model=CommandResponse)
async def review_answer(request: ReviewRequest, services: ServicesDep) -> CommandResponse:
    report = services.reflection.review(request.answer, request.signals)
    services.last_reflection = report
    return CommandResponse(
        detail="metacognitive review completed",
        data=report.model_dump(mode="json"),
    )
