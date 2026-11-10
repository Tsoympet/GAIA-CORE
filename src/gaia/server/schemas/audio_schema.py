"""Pydantic schemas for GAIA audio routes."""
from pydantic import BaseModel


class AudioStatusResponse(BaseModel):
    microphone_enabled: bool = False
    speaker_enabled: bool = False
    text_fallback: bool = True
    synthetic_tone: bool = True
    capture: str = "unavailable"
    playback: str = "synthetic-tone"
    detail: str = (
        "No microphone daemon is attached. Typed text and a synthetic tone "
        "are the local path. This tone is not a cloned voice."
    )
