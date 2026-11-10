"""Metacognitive review over operator-supplied answers."""

from __future__ import annotations

from typing import Annotated, Any

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
    return CommandResponse(
        detail="metacognition ready",
        data={
            "ready": True,
            "external_actions": False,
            "durable": True,
            "last_review": _last_review(services),
        },
    )


@router.post("/review", response_model=CommandResponse)
async def review_answer(request: ReviewRequest, services: ServicesDep) -> CommandResponse:
    report = services.reflection.review(request.answer, request.signals)
    services.last_reflection = report
    payload = report.model_dump(mode="json")
    services.cognition.append(
        "metacognition",
        request.answer,
        {"review": payload, "external_actions": False},
    )
    return CommandResponse(
        detail="metacognitive review completed",
        data=payload,
    )


def _last_review(services: GaiaServices) -> dict[str, Any] | None:
    """Return the newest stored review so a restart keeps the last critique."""
    stored = services.cognition.latest("metacognition")
    if stored is not None:
        review = stored.payload.get("review")
        if isinstance(review, dict):
            return {str(key): value for key, value in review.items()}
    if services.last_reflection is not None:
        dumped: dict[str, Any] = services.last_reflection.model_dump(mode="json")
        return dumped
    return None
