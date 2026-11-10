"""Workspace lifecycle API routes backed by local SQLite persistence."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request

from gaia.core.runtime import GaiaRuntime
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
    body: WorkspaceCreateRequest,
    request: Request,
    services: ServicesDep,
) -> WorkspaceResponse:
    """Create a durable local workspace."""
    try:
        workspace = services.workspaces.create(
            body.name,
            description=body.description,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _workspace_response(workspace, services, _task_ids(_runtime(request)))


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(request: Request, services: ServicesDep) -> list[WorkspaceResponse]:
    """List durable local workspaces."""
    known_tasks = _task_ids(_runtime(request))
    return [
        _workspace_response(workspace, services, known_tasks)
        for workspace in services.workspaces.list()
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    request: Request,
    services: ServicesDep,
) -> WorkspaceResponse:
    """Fetch a durable local workspace by id."""
    workspace = services.workspaces.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    known_tasks = _task_ids(_runtime(request))
    return _workspace_response(workspace, services, known_tasks)


@router.post("/{workspace_id}/links", response_model=WorkspaceLinkResponse)
async def attach_workspace_link(
    workspace_id: str,
    body: WorkspaceLinkCreateRequest,
    request: Request,
    services: ServicesDep,
) -> WorkspaceLinkResponse:
    """Attach a task or memory reference that exists in this process."""
    runtime = _runtime(request)
    ref_id = body.ref_id.strip()
    if not ref_id:
        raise HTTPException(status_code=400, detail="link reference must not be empty")
    known_tasks = _task_ids(runtime)
    if not _reference_exists(body.kind, ref_id, services, known_tasks):
        raise HTTPException(
            status_code=400,
            detail=f"unknown {body.kind} reference: {ref_id}",
        )
    try:
        link = services.workspaces.attach(
            workspace_id,
            body.kind,
            ref_id,
            label=body.label,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _link_response(link, services, known_tasks)


@router.get("/{workspace_id}/links", response_model=list[WorkspaceLinkResponse])
async def list_workspace_links(
    workspace_id: str,
    request: Request,
    services: ServicesDep,
) -> list[WorkspaceLinkResponse]:
    """List task and memory references attached to a workspace."""
    if services.workspaces.get(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    known_tasks = _task_ids(_runtime(request))
    return [
        _link_response(link, services, known_tasks)
        for link in services.workspaces.list_links(workspace_id)
    ]


def _workspace_response(
    workspace: WorkspaceRecord,
    services: GaiaServices,
    known_tasks: set[str],
) -> WorkspaceResponse:
    metadata: dict[str, Any] = dict(workspace.metadata)
    links = [
        _link_response(link, services, known_tasks)
        for link in services.workspaces.list_links(workspace.workspace_id)
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


def _link_response(
    link: WorkspaceLink,
    services: GaiaServices,
    known_tasks: set[str],
) -> WorkspaceLinkResponse:
    return WorkspaceLinkResponse(
        link_id=link.link_id,
        workspace_id=link.workspace_id,
        kind=_link_kind(link.kind),
        ref_id=link.ref_id,
        label=link.label,
        target_exists=_reference_exists(link.kind, link.ref_id, services, known_tasks),
        created_at=link.created_at,
    )


def _runtime(request: Request) -> GaiaRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, GaiaRuntime) or runtime.kernel is None:
        raise HTTPException(status_code=503, detail="runtime is not configured")
    return runtime


def _task_ids(runtime: GaiaRuntime) -> set[str]:
    """Ids an operator can attach: kernel goals and continuity task runs."""
    found = {goal.id for goal in runtime.kernel.goals.list_goals()}
    continuity = runtime.kernel.continuity
    if continuity is not None:
        for task in continuity.store.list_tasks():
            found.add(task.task_id)
            found.add(task.goal_id)
    return found


def _reference_exists(
    kind: str,
    ref_id: str,
    services: GaiaServices,
    known_tasks: set[str],
) -> bool:
    if kind == "memory":
        return services.memory.get_record(ref_id) is not None
    if kind == "task":
        return ref_id in known_tasks
    return False
