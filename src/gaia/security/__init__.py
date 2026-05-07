"""Security foundation exports."""

from .audit_log import AuditEvent, AuditLog, AuditOutcome
from .autonomy import AutonomyKillSwitch, AutonomyPolicy
from .guards import CommandGuard, FileGuard, NetworkGuard
from .permission_manager import Permission, PermissionDecision, PermissionManager, PermissionRule
from .secrets_manager import SecretsManager
from .self_modification import SelfModificationGuard

__all__ = [
    "AuditEvent", "AuditLog", "AuditOutcome", "AutonomyKillSwitch", "AutonomyPolicy",
    "CommandGuard", "FileGuard", "NetworkGuard", "Permission", "PermissionDecision",
    "PermissionManager", "PermissionRule", "SecretsManager", "SelfModificationGuard",
]
"""Security policy, permissions, audit, and autonomy controls."""

from gaia.security.policy import SecurityDecision, SecurityPolicy, create_security_policy

__all__ = ["SecurityDecision", "SecurityPolicy", "create_security_policy"]
