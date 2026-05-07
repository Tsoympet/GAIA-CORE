"""Permission checks, audit logging, and autonomy kill switch for GAIA."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatch

from gaia.security.audit_log import AuditEvent, AuditLog, AuditOutcome


class Permission(StrEnum):
    """Security-sensitive action classes requiring explicit policy decisions."""

    SHELL_COMMAND = "shell.command"
    FILE_DELETE = "file.delete"
    NETWORK_ACCESS = "network.access"
    GITHUB_PUSH = "github.push"
    PACKAGE_INSTALL = "package.install"
    API_KEY_USE = "api_key.use"
    CODE_EXECUTION = "code.execution"
    SCHEDULED_AUTONOMY = "autonomy.scheduled"
    EXTERNAL_COMMUNICATION = "external.communication"
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"


RISKY_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.SHELL_COMMAND,
        Permission.FILE_DELETE,
        Permission.NETWORK_ACCESS,
        Permission.GITHUB_PUSH,
        Permission.PACKAGE_INSTALL,
        Permission.API_KEY_USE,
        Permission.CODE_EXECUTION,
        Permission.SCHEDULED_AUTONOMY,
        Permission.EXTERNAL_COMMUNICATION,
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
    autonomy_kill_switch: bool = False

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
        self, permission: Permission, resource_pattern: str = "*", reason: str = "deny"
    ) -> None:
        """Deny a permission for a resource pattern."""
        self.rules.append(PermissionRule(permission, resource_pattern, False, reason))

    def extend(self, rules: Iterable[PermissionRule]) -> None:
        """Append multiple permission rules."""
        self.rules.extend(rules)

    def activate_kill_switch(self) -> None:
        """Stop all autonomous risky action approvals."""
        self.autonomy_kill_switch = True

    def deactivate_kill_switch(self) -> None:
        """Allow policy evaluation to resume after human intervention."""
        self.autonomy_kill_switch = False

    def check(
        self, permission: Permission, resource: str, actor: str = "system"
    ) -> PermissionDecision:
        """Evaluate permission with deny-by-default and risky-action approval rules."""
        if self.autonomy_kill_switch and permission in RISKY_PERMISSIONS:
            return self._record(
                PermissionDecision(
                    False,
                    permission,
                    resource,
                    actor,
                    "autonomy kill switch active",
                    True,
                    True,
                )
            )
        matched = [
            rule
            for rule in self.rules
            if rule.permission == permission and fnmatch(resource, rule.resource_pattern)
        ]
        if not matched:
            return self._record(
                PermissionDecision(
                    False,
                    permission,
                    resource,
                    actor,
                    "no matching allow rule",
                    permission in RISKY_PERMISSIONS,
                )
            )
        rule = matched[-1]
        requires_approval = permission in RISKY_PERMISSIONS and not rule.human_approved
        allowed = rule.allowed and not requires_approval
        reason = (
            rule.reason
            if allowed
            else "human approval required"
            if requires_approval
            else rule.reason
        )
        return self._record(
            PermissionDecision(allowed, permission, resource, actor, reason, requires_approval)
        )

    def require(self, permission: Permission, resource: str, actor: str = "system") -> None:
        """Raise PermissionError when a permission is denied."""
        decision = self.check(permission, resource, actor)
        if not decision.allowed:
            raise PermissionError(f"{permission.value} denied for {resource}: {decision.reason}")

    def _record(self, decision: PermissionDecision) -> PermissionDecision:
        self.audit_log.record(
            AuditEvent(
                action=decision.permission.value,
                actor=decision.actor,
                resource=decision.resource,
                outcome=AuditOutcome.ALLOWED if decision.allowed else AuditOutcome.DENIED,
                reason=decision.reason,
                metadata={
                    "requires_human_approval": decision.requires_human_approval,
                    "kill_switch_active": decision.kill_switch_active,
                },
            )
        )
        return decision
