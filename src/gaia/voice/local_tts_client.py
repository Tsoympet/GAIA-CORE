"""LocalTTSClient placeholder for GAIA voice architecture."""
from __future__ import annotations

from pydantic import BaseModel


class LocalTTSClient(BaseModel):
    """Typed placeholder for future provider integration."""
    enabled: bool = False
    provider: str = "placeholder"
