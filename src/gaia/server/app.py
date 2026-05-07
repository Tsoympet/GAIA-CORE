"""FastAPI application factory for GAIA Core."""

from __future__ import annotations

from fastapi import FastAPI

from gaia.server.routes import ROUTERS
from gaia.server.schemas import HealthResponse


def create_app() -> FastAPI:
    app = FastAPI(title="GAIA Core API", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    for router in ROUTERS:
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
