"""Policy coordination between security evaluation and permission checks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from gaia.security.permission_manager import Permission, PermissionManager
from gaia.security.policy import SecurityDecision, SecurityPolicy


class PolicyGateDecision(BaseModel):
    """Combined admission decision for a kernel-managed goal."""

    allowed: bool
    requires_human_approval: bool = False
    reasons: list[str] = Field(default_factory=list)
    security: SecurityDecision | None = None
    kill_switch_active: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyCoordinator:
    """Admit goals and gate sensitive actions through shared security state."""

    def __init__(
        self,
        security_policy: SecurityPolicy,
        permission_manager: PermissionManager,
    ) -> None:
        self.security_policy = security_policy
        self.permission_manager = permission_manager

    def admit_goal(
        self,
        objective: str,
        *,
        actor: str = "kernel",
    ) -> PolicyGateDecision:
        """Evaluate whether a goal may enter active execution."""
        if self.permission_manager.kill_switch.enabled:
            return PolicyGateDecision(
                allowed=False,
                requires_human_approval=True,
                reasons=["autonomy kill switch is active"],
                kill_switch_active=True,
                metadata={"actor": actor},
            )

        security = self.security_policy.evaluate_objective(objective)
        if not security.allowed:
            return PolicyGateDecision(
                allowed=False,
                requires_human_approval=security.requires_human_approval,
                reasons=list(security.reasons),
                security=security,
                metadata={"actor": actor},
            )

        return PolicyGateDecision(
            allowed=True,
            requires_human_approval=security.requires_human_approval,
            reasons=[],
            security=security,
            metadata={"actor": actor},
        )

    def check_permission(
        self,
        permission: Permission,
        resource: str = "*",
        *,
        actor: str = "kernel",
    ) -> PolicyGateDecision:
        """Evaluate a fine-grained permission through the shared manager."""
        decision = self.permission_manager.check(
            permission,
            resource,
            actor=actor,
        )
        return PolicyGateDecision(
            allowed=decision.allowed,
            requires_human_approval=decision.requires_human_approval,
            reasons=[decision.reason] if decision.reason else [],
            kill_switch_active=decision.kill_switch_active,
            metadata={
                "permission": permission.value,
                "resource": resource,
                "actor": actor,
            },
        )
