"""Workspace lifecycle API routes backed by local SQLite persistence."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse, WorkspaceCreateRequest, WorkspaceResponse
from gaia.workspaces import WorkspaceRecord

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/status", response_model=CommandResponse)
async def workspace_status(services: ServicesDep) -> CommandResponse:
    """Return durable workspace persistence status."""
    return CommandResponse(detail="workspace persistence ready", data=services.workspaces.status())


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreateRequest,
    services: ServicesDep,
) -> WorkspaceResponse:
    """Create a durable local workspace."""
    try:
        workspace = services.workspaces.create(
            request.name,
            description=request.description,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _workspace_response(workspace)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(services: ServicesDep) -> list[WorkspaceResponse]:
    """List durable local workspaces."""
    return [_workspace_response(workspace) for workspace in services.workspaces.list()]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, services: ServicesDep) -> WorkspaceResponse:
    """Fetch a durable local workspace by id."""
    workspace = services.workspaces.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return _workspace_response(workspace)


def _workspace_response(workspace: WorkspaceRecord) -> WorkspaceResponse:
    metadata: dict[str, Any] = dict(workspace.metadata)
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        description=workspace.description,
        metadata=metadata,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )
