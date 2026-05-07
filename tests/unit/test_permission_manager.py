from gaia.security.permission_manager import Permission, PermissionManager


def test_risky_action_requires_human_approval() -> None:
    manager = PermissionManager()
    manager.grant(Permission.SHELL_COMMAND, "echo *", reason="developer grant")

    decision = manager.check(Permission.SHELL_COMMAND, "echo hello")

    assert decision.allowed is False
    assert decision.requires_human_approval is True


def test_human_approved_risky_action_can_pass_and_kill_switch_blocks() -> None:
    manager = PermissionManager()
    manager.grant(
        Permission.SHELL_COMMAND,
        "echo *",
        reason="approved once",
        human_approved=True,
    )

    assert manager.check(Permission.SHELL_COMMAND, "echo hello").allowed is True
    manager.activate_kill_switch()
    decision = manager.check(Permission.SHELL_COMMAND, "echo hello")
    assert decision.allowed is False
    assert decision.kill_switch_active is True
