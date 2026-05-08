"""Speech-to-text abstraction for GAIA microphone and audio sessions."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class STTRequest(BaseModel):
    audio_path: Path | None = None
    provider: str = "whisper-compatible-placeholder"
    language: str = "en"

class STTResult(BaseModel):
    text: str
    provider: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "placeholder"

class STTEngine:
    """Provider-neutral STT facade with text-only fallback behavior."""
    async def transcribe(self, request: STTRequest) -> STTResult:
        text = "" if request.audio_path else "No audio provided; text-only fallback is active."
        return STTResult(text=text, provider=request.provider)
