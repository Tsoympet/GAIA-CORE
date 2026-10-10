"""FastAPI application for the first runnable GAIA backend."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from gaia.core.runtime import GaiaRuntime, TaskRequest, create_runtime
from gaia.orchestrator.aggregator import AggregatedResponse
from gaia.orchestrator.engine import OrchestrationPlan
from gaia.server.deps import GaiaServices, get_services
from gaia.server.routes import ROUTERS

logger = logging.getLogger(__name__)


class TaskResponse(BaseModel):
    """API response for submitted tasks."""

    runtime_id: str
    result: AggregatedResponse


class VersionResponse(BaseModel):
    """Version and service metadata for operators and clients."""

    name: str = "GAIA Core Runtime"
    version: str = "0.1.0"
    api_version: str = "v1"
    local_first: bool = True
    license: str = "Apache-2.0"


class PlanRequest(BaseModel):
    """Request body for plan-only orchestration."""

    objective: str
    capabilities: list[str] = Field(default_factory=list)


def create_app(runtime: GaiaRuntime | None = None) -> FastAPI:
    """Create a configured GAIA FastAPI app.

    When ``runtime`` is omitted an in-memory kernel store is used. Production
    CLI/server entrypoints should pass a runtime created with
    ``DEFAULT_KERNEL_DB_PATH`` for durable goal persistence.
    """
    runtime = runtime or create_runtime(config_dir=Path("config"))
    app = FastAPI(title="GAIA Core Runtime", version="0.1.0")
    app.state.runtime = runtime
    app.state.services = GaiaServices(
        permissions=runtime.permission_manager,
        security_policy=runtime.security_policy,
    )
    app.dependency_overrides[get_services] = lambda: app.state.services

    for router in ROUTERS:
        app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        logger.info("health_check", extra={"runtime_id": runtime.runtime_id})
        return {"status": "ok", "runtime_id": runtime.runtime_id}

    @app.get("/version", response_model=VersionResponse)
    async def version() -> VersionResponse:
        return VersionResponse(local_first=runtime.status().local_first)

    @app.get("/runtime/status")
    async def runtime_status() -> dict[str, object]:
        return runtime.status().model_dump(mode="json")

    @app.get("/agents")
    async def agents() -> dict[str, Any]:
        return {
            "agents": [
                descriptor.model_dump(mode="json")
                for descriptor in runtime.agent_registry.list_descriptors()
            ]
        }

    @app.get("/capabilities")
    async def capabilities() -> dict[str, Any]:
        return {
            "capabilities": [
                capability.model_dump(mode="json")
                for capability in runtime.capability_router.list_capabilities()
            ]
        }

    @app.get("/runtime/memory/status")
    async def runtime_memory_status() -> dict[str, Any]:
        """Return append-only orchestration-event memory status.

        Scoped user/project memory remains available at ``/memory/status`` through
        the canonical memory router.
        """
        return {
            "status": "ok",
            "backend": "in-memory",
            "records": len(runtime.memory_store.records),
            "append_only": True,
        }

    @app.post("/tasks", response_model=TaskResponse)
    async def submit_task(request: TaskRequest) -> TaskResponse:
        try:
            logger.info("task_submitted", extra={"session_id": request.session_id})
            result = await runtime.submit_task(request)
            return TaskResponse(runtime_id=runtime.runtime_id, result=result)
        except ValueError as exc:
            logger.warning("task_rejected", extra={"error": str(exc)})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("task_failed")
            raise HTTPException(status_code=500, detail="GAIA task execution failed") from exc

    @app.post("/orchestrator/plan", response_model=OrchestrationPlan)
    async def plan(request: PlanRequest) -> OrchestrationPlan:
        try:
            return await runtime.orchestrator.plan(request.objective, request.capabilities)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
