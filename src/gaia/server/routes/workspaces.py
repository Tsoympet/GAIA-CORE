"""Workspace lifecycle API routes backed by local SQLite persistence."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import (
    CommandResponse,
    WorkspaceCreateRequest,
    WorkspaceLinkCreateRequest,
    WorkspaceLinkResponse,
    WorkspaceResponse,
)
from gaia.workspaces import WorkspaceLink, WorkspaceRecord

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
    return _workspace_response(workspace, services)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(services: ServicesDep) -> list[WorkspaceResponse]:
    """List durable local workspaces."""
    return [
        _workspace_response(workspace, services) for workspace in services.workspaces.list()
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, services: ServicesDep) -> WorkspaceResponse:
    """Fetch a durable local workspace by id."""
    workspace = services.workspaces.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return _workspace_response(workspace, services)


@router.post("/{workspace_id}/links", response_model=WorkspaceLinkResponse)
async def attach_workspace_link(
    workspace_id: str,
    request: WorkspaceLinkCreateRequest,
    services: ServicesDep,
) -> WorkspaceLinkResponse:
    """Attach a task or memory reference to a local workspace."""
    try:
        link = services.workspaces.attach(
            workspace_id,
            request.kind,
            request.ref_id,
            label=request.label,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _link_response(link)


@router.get("/{workspace_id}/links", response_model=list[WorkspaceLinkResponse])
async def list_workspace_links(
    workspace_id: str,
    services: ServicesDep,
) -> list[WorkspaceLinkResponse]:
    """List task and memory references attached to a workspace."""
    if services.workspaces.get(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return [_link_response(link) for link in services.workspaces.list_links(workspace_id)]


def _workspace_response(workspace: WorkspaceRecord, services: ServicesDep) -> WorkspaceResponse:
    metadata: dict[str, Any] = dict(workspace.metadata)
    links = [
        _link_response(link) for link in services.workspaces.list_links(workspace.workspace_id)
    ]
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        description=workspace.description,
        metadata=metadata,
        links=links,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


def _link_kind(kind: str) -> Literal["task", "memory"]:
    if kind == "task":
        return "task"
    if kind == "memory":
        return "memory"
    raise ValueError(f"unsupported link kind: {kind}")


def _link_response(link: WorkspaceLink) -> WorkspaceLinkResponse:
    return WorkspaceLinkResponse(
        link_id=link.link_id,
        workspace_id=link.workspace_id,
        kind=_link_kind(link.kind),
        ref_id=link.ref_id,
        label=link.label,
        created_at=link.created_at,
    )
