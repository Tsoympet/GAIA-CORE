"""High-level manager for GAIA voice sessions and providers."""
from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.voice.stt_engine import STTEngine, STTRequest, STTResult
from gaia.voice.tts_engine import TTSEngine, TTSRequest, TTSResult
from gaia.voice.voice_identity_generator import VoiceIdentityGenerator
from gaia.voice.voice_profile import VoiceProfile
from gaia.voice.voice_safety import VoiceSafetyFilter


class VoiceStatus(BaseModel):
    enabled: bool = True
    profile_id: str
    synthetic_identity: bool = True
    local_tts_supported: bool = True
    cloud_tts_supported: bool = False
    stt_supported: bool = True
    text_fallback: bool = True
    safety_filters: list[str] = Field(default_factory=lambda: ["impersonation", "export_approval"])

class VoiceManager:
    """Coordinates synthetic identity, TTS, STT, and safety filters."""
    def __init__(self, profile: VoiceProfile | None = None) -> None:
        self.safety_filter = VoiceSafetyFilter()
        self.profile = profile or VoiceIdentityGenerator().generate_default()
        self.tts_engine = TTSEngine(self.safety_filter)
        self.stt_engine = STTEngine()

    def status(self) -> VoiceStatus:
        return VoiceStatus(
            profile_id=self.profile.profile_id,
            synthetic_identity=self.profile.synthetic,
        )

    async def synthesize(self, text: str, provider: str = "local-placeholder") -> TTSResult:
        return await self.tts_engine.synthesize(
            TTSRequest(text=text, provider=provider, profile=self.profile)
        )

    async def transcribe(self, request: STTRequest | None = None) -> STTResult:
        return await self.stt_engine.transcribe(request or STTRequest())
