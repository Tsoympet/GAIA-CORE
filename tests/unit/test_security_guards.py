from pathlib import Path

import pytest

from gaia.security import CommandGuard, FileGuard, NetworkGuard, Permission, PermissionManager


def test_command_guard_requires_approved_shell_permission() -> None:
    permissions = PermissionManager()
    guard = CommandGuard(permissions)

    with pytest.raises(PermissionError, match="no matching allow rule"):
        guard.validate("echo hello")

    permissions.grant(
        Permission.SHELL_COMMAND,
        "echo *",
        reason="operator-approved test command",
        human_approved=True,
    )

    assert guard.validate("echo hello") == "echo hello"


def test_command_guard_blocks_dangerous_prefix_even_when_granted() -> None:
    permissions = PermissionManager()
    permissions.grant(
        Permission.SHELL_COMMAND,
        "*",
        reason="broad test grant",
        human_approved=True,
    )
    guard = CommandGuard(permissions)

    with pytest.raises(PermissionError, match="blocked command prefix"):
        guard.validate("rm -rf workspace")


def test_file_guard_confines_access_to_workspace(tmp_path: Path) -> None:
    permissions = PermissionManager()
    permissions.grant(Permission.FILE_READ, "*", reason="test read")
    guard = FileGuard(permissions, root=tmp_path)

    assert guard.require_read("project/input.txt") == (tmp_path / "project/input.txt").resolve()

    with pytest.raises(PermissionError, match="path escapes workspace root"):
        guard.require_read("../outside.txt")


def test_network_guard_requires_approved_network_permission() -> None:
    permissions = PermissionManager()
    guard = NetworkGuard(permissions, blocked_hosts={"blocked.example"})

    with pytest.raises(PermissionError, match="no matching allow rule"):
        guard.validate_url("https://example.com/research")

    permissions.grant(
        Permission.NETWORK_ACCESS,
        "example.com",
        reason="operator-approved endpoint",
        human_approved=True,
    )

    assert guard.validate_url("https://example.com/research") == "https://example.com/research"

    with pytest.raises(PermissionError, match="blocked network host"):
        guard.validate_url("https://blocked.example/path")
