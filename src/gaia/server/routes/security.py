"""Security route module."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from gaia.security.permission_manager import Permission
from gaia.server.deps import GaiaServices, get_services
from gaia.server.schemas import CommandResponse, PermissionCheckRequest

router = APIRouter(prefix="/security", tags=["security"])
ServicesDep = Annotated[GaiaServices, Depends(get_services)]


@router.get("/status")
async def security_status(services: ServicesDep) -> dict[str, Any]:
    """Return the state used by permission checks and API controls."""
    return {
        "status": "ok",
        "sandbox_required": services.security_policy.sandbox_required,
        "human_override_available": (
            services.security_policy.human_override_available
        ),
        "autonomy_kill_switch": services.kill_switch.enabled,
        "kill_switch_reason": services.kill_switch.reason,
        "risky_actions_require_permission": True,
    }


@router.get("/permissions", response_model=CommandResponse)
async def list_permissions(services: ServicesDep) -> CommandResponse:
    """List allow and deny rules. This does not grant a permission."""
    rules = [
        {
            "permission": rule.permission.value,
            "resource_pattern": rule.resource_pattern,
            "allowed": rule.allowed,
            "reason": rule.reason,
            "human_approved": rule.human_approved,
        }
        for rule in services.permissions.rules
    ]
    return CommandResponse(
        detail="permission rules",
        data={
            "rules": rules,
            "count": len(rules),
            "kill_switch": services.kill_switch.enabled,
        },
    )


@router.get("/audit", response_model=CommandResponse)
async def audit_events(services: ServicesDep, limit: int = 50) -> CommandResponse:
    """Return recent permission decisions. Secret values are not stored here."""
    bounded = min(max(limit, 1), 200)
    events = [
        {
            "event_id": event.event_id,
            "action": event.action,
            "actor": event.actor,
            "outcome": event.outcome.value,
            "reason": event.reason,
            "resource": event.resource,
            "created_at": event.created_at.isoformat(),
            "metadata": event.metadata,
        }
        for event in services.permissions.audit_log.recent(bounded)
    ]
    return CommandResponse(detail="audit events", data={"events": events, "count": len(events)})


@router.post("/check", response_model=CommandResponse)
async def check_permission(
    request: PermissionCheckRequest,
    services: ServicesDep,
) -> CommandResponse:
    """Evaluate one permission. Risky actions stay denied without human approval."""
    try:
        permission = Permission(request.permission)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unknown permission") from exc
    decision = services.permissions.check(
        permission,
        request.resource,
        actor=request.actor,
    )
    return CommandResponse(
        accepted=decision.allowed,
        detail=decision.reason,
        data={
            "allowed": decision.allowed,
            "permission": decision.permission.value,
            "resource": decision.resource,
            "actor": decision.actor,
            "reason": decision.reason,
            "requires_human_approval": decision.requires_human_approval,
            "kill_switch_active": decision.kill_switch_active,
        },
    )


@router.post("/kill-switch", response_model=CommandResponse)
async def trigger_kill_switch(
    reason: str,
    services: ServicesDep,
) -> CommandResponse:
    services.permissions.activate_kill_switch(reason)
    return CommandResponse(
        detail="autonomy kill switch triggered",
        data={"reason": reason},
    )


@router.delete("/kill-switch", response_model=CommandResponse)
async def reset_kill_switch(
    services: ServicesDep,
) -> CommandResponse:
    services.permissions.deactivate_kill_switch()
    return CommandResponse(detail="autonomy kill switch reset")
