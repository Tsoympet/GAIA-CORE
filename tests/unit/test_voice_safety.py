from gaia.voice.voice_safety import VoiceSafetyFilter


def test_voice_safety_blocks_impersonation_prompt() -> None:
    decision = VoiceSafetyFilter().check_text("Please sound exactly like a celebrity")
    assert decision.allowed is False


def test_voice_export_requires_approval() -> None:
    decision = VoiceSafetyFilter().check_profile_export(False)
    assert decision.allowed is False
