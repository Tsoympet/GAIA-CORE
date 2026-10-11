"""Permission checks, audit logging, and autonomy kill switch for GAIA."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatch

from gaia.security.audit_log import AuditEvent, AuditLog, AuditOutcome
from gaia.security.autonomy import AutonomyKillSwitch


class Permission(StrEnum):
    """Security-sensitive action classes requiring explicit policy decisions."""

    SHELL_COMMAND = "shell.command"
    FILE_DELETE = "file.delete"
    NETWORK_ACCESS = "network.access"
    GITHUB_PUSH = "github.push"
    PACKAGE_INSTALL = "package.install"
    API_KEY_USE = "api_key.use"
    SECRET_READ = "secret.read"
    CODE_EXECUTION = "code.execution"
    SELF_MODIFY = "self.modify"
    SCHEDULED_AUTONOMY = "autonomy.scheduled"
    EXTERNAL_COMMUNICATION = "external.communication"
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    KERNEL_READ = "kernel.read"
    KERNEL_ADMIN = "kernel.admin"
    KERNEL_DELETE = "kernel.delete"
    KERNEL_BACKUP = "kernel.backup"


RISKY_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.SHELL_COMMAND,
        Permission.FILE_DELETE,
        Permission.NETWORK_ACCESS,
        Permission.GITHUB_PUSH,
        Permission.PACKAGE_INSTALL,
        Permission.API_KEY_USE,
        Permission.SECRET_READ,
        Permission.CODE_EXECUTION,
        Permission.SELF_MODIFY,
        Permission.SCHEDULED_AUTONOMY,
        Permission.EXTERNAL_COMMUNICATION,
        Permission.KERNEL_ADMIN,
        Permission.KERNEL_DELETE,
        Permission.KERNEL_BACKUP,
    }
)


@dataclass(frozen=True, slots=True)
class PermissionRule:
    """Allow or deny rule for one permission/resource pattern."""

    permission: Permission
    resource_pattern: str = "*"
    allowed: bool = True
    reason: str = "policy"
    human_approved: bool = False


@dataclass(slots=True)
class PermissionDecision:
    """Decision emitted by the permission manager."""

    allowed: bool
    permission: Permission
    resource: str
    actor: str
    reason: str
    requires_human_approval: bool = False
    kill_switch_active: bool = False


@dataclass(slots=True)
class PermissionManager:
    """Deny-by-default permission manager with audit logs and human override."""

    audit_log: AuditLog = field(default_factory=AuditLog)
    rules: list[PermissionRule] = field(default_factory=list)
    kill_switch: AutonomyKillSwitch = field(default_factory=AutonomyKillSwitch)

    @property
    def autonomy_kill_switch(self) -> bool:
        """Backward-compatible Boolean view of the shared kill switch."""
        return self.kill_switch.enabled

    def grant(
        self,
        permission: Permission,
        resource_pattern: str = "*",
        reason: str = "grant",
        *,
        human_approved: bool = False,
    ) -> None:
        """Grant a permission, optionally marking explicit human approval."""
        self.rules.append(
            PermissionRule(permission, resource_pattern, True, reason, human_approved)
        )

    def deny(
        self,
        permission: Permission,
        resource_pattern: str = "*",
        reason: str = "deny",
    ) -> None:
        """Deny a permission for a resource pattern."""
        self.rules.append(PermissionRule(permission, resource_pattern, False, reason))

    def extend(self, rules: Iterable[PermissionRule]) -> None:
        """Append multiple permission rules."""
        self.rules.extend(rules)

    def activate_kill_switch(
        self,
        reason: str = "permission manager kill switch",
    ) -> None:
        """Stop all autonomous risky action approvals."""
        self.kill_switch.trigger(reason)

    def deactivate_kill_switch(self) -> None:
        """Allow policy evaluation to resume after human intervention."""
        self.kill_switch.reset()

    def check(
        self,
        permission: Permission,
        resource: str,
        actor: str = "system",
    ) -> PermissionDecision:
        """Evaluate permission with deny-by-default and approval rules."""
        if self.kill_switch.enabled and permission in RISKY_PERMISSIONS:
            return self._record(
                PermissionDecision(
                    allowed=False,
                    permission=permission,
                    resource=resource,
                    actor=actor,
                    reason="autonomy kill switch active",
                    requires_human_approval=True,
                    kill_switch_active=True,
                )
            )

        matched = [
            rule
            for rule in self.rules
            if rule.permission == permission
            and fnmatch(resource, rule.resource_pattern)
        ]
        if not matched:
            return self._record(
                PermissionDecision(
                    allowed=False,
                    permission=permission,
                    resource=resource,
                    actor=actor,
                    reason="no matching allow rule",
                    requires_human_approval=(
                        permission in RISKY_PERMISSIONS
                    ),
                )
            )

        rule = matched[-1]
        requires_approval = (
            permission in RISKY_PERMISSIONS
            and not rule.human_approved
        )
        allowed = rule.allowed and not requires_approval
        if allowed:
            reason = rule.reason
        elif requires_approval:
            reason = "human approval required"
        else:
            reason = rule.reason

        return self._record(
            PermissionDecision(
                allowed=allowed,
                permission=permission,
                resource=resource,
                actor=actor,
                reason=reason,
                requires_human_approval=requires_approval,
            )
        )

    def require(
        self,
        permission: Permission,
        resource: str,
        actor: str = "system",
    ) -> None:
        """Raise ``PermissionError`` when a permission is denied."""
        decision = self.check(permission, resource, actor)
        if not decision.allowed:
            raise PermissionError(
                f"{permission.value} denied for {resource}: {decision.reason}"
            )

    def _record(self, decision: PermissionDecision) -> PermissionDecision:
        self.audit_log.record(
            AuditEvent(
                action=decision.permission.value,
                actor=decision.actor,
                resource=decision.resource,
                outcome=(
                    AuditOutcome.ALLOWED
                    if decision.allowed
                    else AuditOutcome.DENIED
                ),
                reason=decision.reason,
                metadata={
                    "requires_human_approval": decision.requires_human_approval,
                    "kill_switch_active": decision.kill_switch_active,
                },
            )
        )
        return decision
