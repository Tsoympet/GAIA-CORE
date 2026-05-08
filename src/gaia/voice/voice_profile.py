"""Voice profile model for GAIA's synthetic voice identity."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class VoiceProfile(BaseModel):
    """Configures a synthetic voice profile stored locally by default."""
    profile_id: str = "gaia-default"
    display_name: str = "GAIA Synthetic Voice"
    synthetic: bool = True
    consent_verified: bool = True
    clone_source: str | None = None
    locale: str = "en-US"
    tone: str = "calm"
    emotion: str = "neutral"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    local_storage_path: Path = Path("data/voice_profiles/gaia-default.json")
    export_requires_approval: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def validate_safety(self) -> None:
        """Reject unapproved real-person cloning or impersonation profiles."""
        if not self.synthetic and not self.consent_verified:
            raise ValueError("real-person voice profiles require explicit consent")
        if self.clone_source and not self.consent_verified:
            raise ValueError("voice cloning requires explicit permission")
