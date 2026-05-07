import pytest

from gaia.dreaming.no_action_guard import NoActionGuard


def test_dreaming_no_action_guard_blocks_external_actions() -> None:
    guard = NoActionGuard()

    assert guard.check("simulate").allowed is True
    assert guard.check("network.access").allowed is False
    with pytest.raises(PermissionError):
        guard.require("shell.command")
