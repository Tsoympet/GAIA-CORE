"""Pydantic schemas for GAIA audio routes."""
from pydantic import BaseModel


class AudioStatusResponse(BaseModel):
    microphone_enabled: bool = False
    speaker_enabled: bool = False
    text_fallback: bool = True
