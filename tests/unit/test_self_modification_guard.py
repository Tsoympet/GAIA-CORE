from pathlib import Path

import pytest

from gaia.security import Permission, PermissionManager, SelfModificationGuard


def test_self_modification_requires_change_approval_and_permission() -> None:
    permissions = PermissionManager()
    guard = SelfModificationGuard(permissions)
    target = Path("src/gaia/security/policy.py")

    with pytest.raises(PermissionError, match="human approval required"):
        guard.validate(target, change_id=None)

    guard.approve("change-1")
    with pytest.raises(PermissionError, match="no matching allow rule"):
        guard.validate(target, change_id="change-1")

    permissions.grant(
        Permission.SELF_MODIFY,
        "src/gaia/security/*",
        reason="operator-approved recovery change",
        human_approved=True,
    )

    guard.validate(target, change_id="change-1")


def test_self_modification_rejects_unknown_change_id() -> None:
    permissions = PermissionManager()
    permissions.grant(
        Permission.SELF_MODIFY,
        "*",
        reason="operator-approved recovery change",
        human_approved=True,
    )
    guard = SelfModificationGuard(permissions)

    with pytest.raises(PermissionError, match="unapproved self-modification"):
        guard.validate("README.md", change_id="unknown")


def test_self_modification_rejects_empty_approval_id() -> None:
    guard = SelfModificationGuard(PermissionManager())

    with pytest.raises(ValueError, match="change_id must not be empty"):
        guard.approve("   ")
