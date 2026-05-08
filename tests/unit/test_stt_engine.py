import pytest

from gaia.voice.stt_engine import STTEngine, STTRequest


@pytest.mark.asyncio
async def test_stt_engine_fallback_without_audio() -> None:
    result = await STTEngine().transcribe(STTRequest())
    assert "text-only fallback" in result.text
