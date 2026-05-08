import pytest

from gaia.voice.tts_engine import TTSEngine, TTSRequest


@pytest.mark.asyncio
async def test_tts_engine_text_fallback() -> None:
    result = await TTSEngine().synthesize(TTSRequest(text="Safe synthetic output"))
    assert result.provider == "local-placeholder"
    assert result.audio_path is None
