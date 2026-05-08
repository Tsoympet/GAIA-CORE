"""Audio API routes."""
from fastapi import APIRouter

from gaia.server.schemas.audio_schema import AudioStatusResponse

router = APIRouter(prefix="/audio", tags=["audio"])
@router.get("/status", response_model=AudioStatusResponse)
async def audio_status() -> AudioStatusResponse:
    return AudioStatusResponse()
