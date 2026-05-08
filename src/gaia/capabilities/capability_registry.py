"""Capability catalog for GAIA model, tool, and agent routing."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Capability(BaseModel):
    """A routable capability exposed by GAIA."""

    name: str
    description: str
    risky_actions: list[str] = Field(default_factory=list)


class CapabilityRegistry:
    """In-memory catalog of GAIA capabilities."""

    def __init__(self, capabilities: list[Capability] | None = None) -> None:
        self._capabilities = {capability.name: capability for capability in capabilities or []}

    def register(self, capability: Capability) -> None:
        """Register or replace a capability."""
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability:
        """Return a capability by name."""
        try:
            return self._capabilities[name]
        except KeyError as exc:
            raise KeyError(f"capability is not registered: {name}") from exc

    def list(self) -> list[Capability]:
        """Return capabilities in stable order."""
        return [self._capabilities[name] for name in sorted(self._capabilities)]

    def names(self) -> list[str]:
        """Return capability names in stable order."""
        return sorted(self._capabilities)


def create_default_capability_registry() -> CapabilityRegistry:
    """Create GAIA's initial local-first capability catalog."""
    entries = [
        ("reasoning", "General reasoning and synthesis."),
        ("planning", "Task decomposition and execution planning."),
        ("research", "Research and evidence gathering."),
        ("coding", "Software engineering with permission-checked execution."),
        ("tooling", "Audited tool and skill execution."),
        ("engineering", "Engineering analysis workflows."),
        ("vision", "Visual and multimodal analysis."),
        ("audio", "Audio processing and transcription."),
        ("voice", "Synthetic voice identity, text-to-speech, and voice conversations."),
        ("speech", "Speech-to-text and spoken interaction."),
        ("tts", "Text-to-speech synthesis."),
        ("stt", "Speech-to-text transcription."),
        ("wake_word", "Local wake word detection."),
        ("documents", "Document, PDF, and spreadsheet reasoning."),
        ("repo", "Repository and version-control analysis."),
        ("cad", "CAD and engineering artifact workflows."),
        ("memory", "Persistent memory recall and consolidation."),
        ("security", "Policy enforcement and audit review."),
        ("self_model", "Simulated self-model and capability mapping."),
        ("metacognition", "Confidence estimation and reflective review."),
        ("reflection", "Post-execution reflection and self-critique."),
        ("dreaming", "Safe idle cognition and replay simulation."),
        ("idle_reflection", "Internal-only idle analysis and consolidation."),
        ("plugins", "External plugin discovery and governance."),
        ("self_evolve", "Human-approved platform improvement proposal generation."),
    ]
    return CapabilityRegistry([Capability(name=name, description=desc) for name, desc in entries])
