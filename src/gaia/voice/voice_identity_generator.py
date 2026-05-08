"""Synthetic GAIA voice identity generation."""
from __future__ import annotations

from gaia.voice.voice_profile import VoiceProfile


class VoiceIdentityGenerator:
    """Creates a unique synthetic voice identity without cloning real people."""
    def generate_default(self) -> VoiceProfile:
        return VoiceProfile(tone="warm", emotion="neutral", speed=1.0, pitch=1.0)
