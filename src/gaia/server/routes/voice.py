"""Voice API routes."""
from __future__ import annotations

from fastapi import APIRouter

from gaia.server.schemas.voice_schema import (
    VoiceStatusResponse,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from gaia.voice.voice_manager import VoiceManager

router = APIRouter(prefix="/voice", tags=["voice"])
_voice_manager = VoiceManager()

@router.get("/status", response_model=VoiceStatusResponse)
async def voice_status() -> VoiceStatusResponse:
    return VoiceStatusResponse(**_voice_manager.status().model_dump())

@router.post("/synthesize", response_model=VoiceSynthesisResponse)
async def synthesize_voice(request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
    result = await _voice_manager.synthesize(request.text, provider=request.provider)
    return VoiceSynthesisResponse(
        text=result.text,
        provider=result.provider,
        status=result.status,
        synthetic=result.synthetic,
        audio_path=str(result.audio_path) if result.audio_path else None,
    )
