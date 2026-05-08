"""Safety filters for GAIA voice input, output, and model export."""
from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceSafetyDecision(BaseModel):
    allowed: bool
    reason: str
    flags: list[str] = Field(default_factory=list)


class VoiceSafetyFilter:
    """Blocks unsafe voice generation, undisclosed cloning, and export without approval."""
    blocked_phrases = ("imitate a real person", "clone celebrity", "sound exactly like")

    def check_text(self, text: str) -> VoiceSafetyDecision:
        lowered = text.lower()
        flags = [phrase for phrase in self.blocked_phrases if phrase in lowered]
        if flags:
            return VoiceSafetyDecision(
                allowed=False,
                reason="voice output may not request real-person impersonation",
                flags=flags,
            )
        return VoiceSafetyDecision(allowed=True, reason="voice output accepted")

    def check_profile_export(self, approved: bool) -> VoiceSafetyDecision:
        if not approved:
            return VoiceSafetyDecision(
                allowed=False,
                reason="voice model export requires explicit user approval",
                flags=["export_approval"],
            )
        return VoiceSafetyDecision(allowed=True, reason="voice export approved")
