"""Speech capabilities advertised by GAIA."""
from gaia.capabilities.capability_registry import Capability
SPEECH_CAPABILITIES = [Capability(name="speech", description="Speech-to-text, microphone input, and transcript handling."), Capability(name="tts", description="Text-to-speech through local providers with text fallback."), Capability(name="stt", description="Whisper-compatible speech transcription.")]
