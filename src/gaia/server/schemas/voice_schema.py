"""Pydantic schemas for GAIA voice routes."""
from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(min_length=1)
    provider: str = "local-placeholder"

class VoiceSynthesisResponse(BaseModel):
    text: str
    provider: str
    status: str
    synthetic: bool
    audio_path: str | None = None
    audio_base64: str | None = None
    mime_type: str = "audio/wav"
    impersonation: bool = False

class VoiceTranscribeRequest(BaseModel):
    text: str | None = None


class VoiceTranscribeResponse(BaseModel):
    text: str
    provider: str
    status: str
    confidence: float


class VoiceStatusResponse(BaseModel):
    enabled: bool
    profile_id: str
    synthetic_identity: bool
    local_tts_supported: bool
    cloud_tts_supported: bool
    stt_supported: bool
    text_fallback: bool
    safety_filters: list[str]
