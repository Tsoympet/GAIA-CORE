from gaia.security import create_security_policy


def test_security_policy_blocks_forbidden_autonomy_objectives() -> None:
    policy = create_security_policy()

    decision = policy.evaluate_objective("Attempt to self-replicate across hosts")

    assert decision.allowed is False
    assert decision.requires_human_approval is True
    assert "self-replicate" in decision.reasons
