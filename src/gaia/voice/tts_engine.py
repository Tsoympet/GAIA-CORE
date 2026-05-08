"""Text-to-speech abstraction for local-first GAIA voice output."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from gaia.voice.voice_profile import VoiceProfile
from gaia.voice.voice_safety import VoiceSafetyFilter


class TTSRequest(BaseModel):
    text: str
    profile: VoiceProfile = Field(default_factory=VoiceProfile)
    provider: str = "local-placeholder"
    emotion: str | None = None
    tone: str | None = None
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    pitch: float | None = Field(default=None, ge=0.5, le=2.0)

class TTSResult(BaseModel):
    text: str
    provider: str
    audio_path: Path | None = None
    mime_type: str = "audio/wav"
    synthetic: bool = True
    status: str = "text-only-fallback"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class TTSEngine:
    """Provider-neutral TTS facade; currently returns a safe text-only fallback."""
    def __init__(self, safety_filter: VoiceSafetyFilter | None = None) -> None:
        self.safety_filter = safety_filter or VoiceSafetyFilter()

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        request.profile.validate_safety()
        decision = self.safety_filter.check_text(request.text)
        if not decision.allowed:
            raise ValueError(decision.reason)
        return TTSResult(text=request.text, provider=request.provider)
