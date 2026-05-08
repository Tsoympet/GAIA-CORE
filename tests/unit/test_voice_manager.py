import pytest

from gaia.voice.voice_manager import VoiceManager


@pytest.mark.asyncio
async def test_voice_manager_status_and_synthesis() -> None:
    manager = VoiceManager()
    status = manager.status()
    assert status.synthetic_identity is True
    result = await manager.synthesize("Hello GAIA")
    assert result.status == "text-only-fallback"
    assert result.synthetic is True
