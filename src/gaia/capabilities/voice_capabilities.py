"""Voice capabilities advertised by GAIA."""

from gaia.capabilities.capability_registry import Capability

VOICE_CAPABILITIES = [
    Capability(
        name="voice",
        description=(
            "Synthetic voice identity, TTS, voice conversation, "
            "and voice safety."
        ),
    ),
    Capability(
        name="wake_word",
        description="Wake word detection with local-first processing.",
    ),
]
