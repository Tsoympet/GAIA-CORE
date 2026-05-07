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
"""FastAPI application factory for GAIA."""

from pathlib import Path

from fastapi import FastAPI

from gaia.core.runtime import create_runtime
from gaia.orchestrator.engine import OrchestrationPlan


def create_app() -> FastAPI:
    """Create the GAIA API server."""
    runtime = create_runtime(config_dir=Path("config"))
    app = FastAPI(
        title="GAIA Core API",
        version="0.1.0",
        description="Typed API for GAIA runtime, orchestration, memory, and capability discovery.",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "runtime_id": runtime.runtime_id}

    @app.get("/runtime/status")
    async def runtime_status() -> dict[str, object]:
        return runtime.status().model_dump(mode="json")

    @app.post("/orchestrator/plan")
    async def plan(objective: str, capabilities: list[str] | None = None) -> OrchestrationPlan:
        return await runtime.orchestrator.plan(objective=objective, capabilities=capabilities or [])

    return app
