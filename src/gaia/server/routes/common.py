"""Shared route helpers."""

from __future__ import annotations

from fastapi import APIRouter

from gaia.server.schemas import CommandResponse


def status_router(prefix: str, tag: str, summary: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("/status", response_model=CommandResponse)
    async def status() -> CommandResponse:
        return CommandResponse(detail=f"{summary} foundation route ready")

    return router
