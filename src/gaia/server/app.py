"""FastAPI application for the first runnable GAIA backend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from gaia.core.runtime import GaiaRuntime, TaskRequest, create_runtime
from gaia.orchestrator.aggregator import AggregatedResponse
from gaia.orchestrator.engine import OrchestrationPlan


class TaskResponse(BaseModel):
    """API response for submitted tasks."""

    runtime_id: str
    result: AggregatedResponse


class PlanRequest(BaseModel):
    """Request body for plan-only orchestration."""

    objective: str
    capabilities: list[str] = Field(default_factory=list)


def create_app(runtime: GaiaRuntime | None = None) -> FastAPI:
    """Create a configured GAIA FastAPI app."""
    runtime = runtime or create_runtime(config_dir=Path("config"))
    app = FastAPI(title="GAIA Core Runtime", version="0.1.0")
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "runtime_id": runtime.runtime_id}

    @app.get("/runtime/status")
    async def runtime_status() -> dict[str, object]:
        return runtime.status().model_dump(mode="json")

    @app.post("/tasks", response_model=TaskResponse)
    async def submit_task(request: TaskRequest) -> TaskResponse:
        result = await runtime.submit_task(request)
        return TaskResponse(runtime_id=runtime.runtime_id, result=result)

    @app.post("/orchestrator/plan", response_model=OrchestrationPlan)
    async def plan(request: PlanRequest) -> OrchestrationPlan:
        return await runtime.orchestrator.plan(request.objective, request.capabilities)

    return app


app = create_app()
