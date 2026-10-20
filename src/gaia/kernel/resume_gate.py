"""Refuse resume when a named permission or resource budget is stale.

A capability is checked only when its name is a permission identifier.
Routing labels are left alone. The check does not grant a permission and
does not reset budget counters.
"""

from __future__ import annotations

from collections.abc import Sequence

from gaia.kernel.policy_coordinator import PolicyCoordinator
from gaia.kernel.resource_budget import BudgetSnapshot
from gaia.security.permission_manager import Permission


def named_permissions(capabilities: Sequence[str]) -> list[Permission]:
    """Return permission identifiers named by a goal, in capability order."""
    known = {item.value: item for item in Permission}
    found: list[Permission] = []
    for name in capabilities:
        permission = known.get(name)
        if permission is None or permission in found:
            continue
        found.append(permission)
    return found


def first_denied_permission(
    capabilities: Sequence[str],
    policy: PolicyCoordinator,
) -> Permission | None:
    """Return the first named permission the live policy does not allow."""
    for permission in named_permissions(capabilities):
        decision = policy.check_permission(permission, "*")
        if not decision.allowed:
            return permission
    return None


def exhausted_resume_resource(snapshot: BudgetSnapshot) -> str | None:
    """Return a resource resume must not continue.

    Resume consumes another step, so a step counter already at its limit is
    exhausted even when the snapshot has not recorded that name yet.
    """
    if snapshot.exhausted_resource:
        return snapshot.exhausted_resource
    checks = (
        ("steps", snapshot.steps_used, snapshot.budget.max_steps),
        ("model_calls", snapshot.model_calls_used, snapshot.budget.max_model_calls),
        ("tool_calls", snapshot.tool_calls_used, snapshot.budget.max_tool_calls),
        ("wall_ms", snapshot.wall_ms_used, snapshot.budget.max_wall_ms),
        ("context_items", snapshot.context_items_used, snapshot.budget.max_context_items),
        ("memory_writes", snapshot.memory_writes_used, snapshot.budget.max_memory_writes),
    )
    for name, used, limit in checks:
        if used > limit:
            return name
    if snapshot.steps_used >= snapshot.budget.max_steps:
        return "steps"
    return None
