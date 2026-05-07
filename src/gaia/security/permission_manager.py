"""Capability-oriented permission manager used by GAIA guards."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatch
from typing import Iterable

from .audit_log import AuditEvent, AuditLog, AuditOutcome


class Permission(StrEnum):
    COMMAND_EXECUTE = "command.execute"
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    NETWORK_CONNECT = "network.connect"
    SECRET_READ = "secret.read"
    SELF_MODIFY = "self.modify"
    AUTONOMY_RUN = "autonomy.run"


@dataclass(frozen=True, slots=True)
class PermissionRule:
    permission: Permission
    resource_pattern: str = "*"
    allowed: bool = True
    reason: str = "policy"


@dataclass(slots=True)
class PermissionDecision:
    allowed: bool
    permission: Permission
    resource: str
    actor: str
    reason: str


@dataclass(slots=True)
class PermissionManager:
    """Evaluates explicit allow/deny rules with deny-by-default semantics."""

    audit_log: AuditLog = field(default_factory=AuditLog)
    rules: list[PermissionRule] = field(default_factory=list)

    def grant(self, permission: Permission, resource_pattern: str = "*", reason: str = "grant") -> None:
        self.rules.append(PermissionRule(permission, resource_pattern, True, reason))

    def deny(self, permission: Permission, resource_pattern: str = "*", reason: str = "deny") -> None:
        self.rules.append(PermissionRule(permission, resource_pattern, False, reason))

    def extend(self, rules: Iterable[PermissionRule]) -> None:
        self.rules.extend(rules)

    def check(self, permission: Permission, resource: str, actor: str = "system") -> PermissionDecision:
        matched = [r for r in self.rules if r.permission == permission and fnmatch(resource, r.resource_pattern)]
        if not matched:
            decision = PermissionDecision(False, permission, resource, actor, "no matching allow rule")
        else:
            rule = matched[-1]
            decision = PermissionDecision(rule.allowed, permission, resource, actor, rule.reason)
        self.audit_log.record(
            AuditEvent(
                action=permission.value,
                actor=actor,
                resource=resource,
                outcome=AuditOutcome.ALLOWED if decision.allowed else AuditOutcome.DENIED,
                reason=decision.reason,
            )
        )
        return decision

    def require(self, permission: Permission, resource: str, actor: str = "system") -> None:
        decision = self.check(permission, resource, actor)
        if not decision.allowed:
            raise PermissionError(f"{permission.value} denied for {resource}: {decision.reason}")
