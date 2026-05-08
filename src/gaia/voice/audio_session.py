"""AudioSession placeholder for GAIA voice architecture."""
from __future__ import annotations

from pydantic import BaseModel


class AudioSession(BaseModel):
    """Typed placeholder for future provider integration."""
    enabled: bool = False
    provider: str = "placeholder"
