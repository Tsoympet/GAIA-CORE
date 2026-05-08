"""MicrophoneInput placeholder for GAIA voice architecture."""
from __future__ import annotations

from pydantic import BaseModel


class MicrophoneInput(BaseModel):
    """Typed placeholder for future provider integration."""
    enabled: bool = False
    provider: str = "placeholder"
