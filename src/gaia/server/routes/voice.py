"""Voice API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gaia.server.schemas.voice_schema import (
    VoiceStatusResponse,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
    VoiceTranscribeRequest,
    VoiceTranscribeResponse,
)
from gaia.voice.voice_manager import VoiceManager

router = APIRouter(prefix="/voice", tags=["voice"])
_voice_manager = VoiceManager()

@router.get("/status", response_model=VoiceStatusResponse)
async def voice_status() -> VoiceStatusResponse:
    return VoiceStatusResponse(**_voice_manager.status().model_dump())

@router.post("/synthesize", response_model=VoiceSynthesisResponse)
async def synthesize_voice(request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
    try:
        result = await _voice_manager.synthesize(request.text, provider=request.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VoiceSynthesisResponse(
        text=result.text,
        provider=result.provider,
        status=result.status,
        synthetic=result.synthetic,
        audio_path=str(result.audio_path) if result.audio_path else None,
        audio_base64=result.audio_base64,
        mime_type=result.mime_type,
        impersonation=False,
    )


@router.post("/transcribe", response_model=VoiceTranscribeResponse)
async def transcribe_voice(request: VoiceTranscribeRequest) -> VoiceTranscribeResponse:
    """Accept operator text when no microphone daemon is attached."""
    if request.text and request.text.strip():
        return VoiceTranscribeResponse(
            text=request.text.strip(),
            provider="operator-text",
            status="text-fallback",
            confidence=1.0,
        )
    result = await _voice_manager.transcribe()
    return VoiceTranscribeResponse(
        text=result.text,
        provider=result.provider,
        status=result.status,
        confidence=result.confidence,
    )
