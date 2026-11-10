"""Safe simulated self-model for GAIA; this is not sentience or consciousness."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gaia.self_model.capability_self_map import CapabilitySelfMap
from gaia.self_model.limitation_registry import Limitation, LimitationRegistry


class SelfModelSnapshot(BaseModel):
    """Introspection snapshot emitted by the simulated self-model."""

    identity: str
    statement: str
    capabilities: list[str] = Field(default_factory=list)
    limitations: list[Limitation] = Field(default_factory=list)


class SimulatedSelfModel:
    """Engineering introspection layer for capability and limitation awareness."""

    def __init__(
        self,
        capability_map: CapabilitySelfMap | None = None,
        limitations: LimitationRegistry | None = None,
    ) -> None:
        self.capability_map = capability_map or CapabilitySelfMap()
        self.limitations = limitations or LimitationRegistry()

    def snapshot(self) -> SelfModelSnapshot:
        """Return a safe self-description without consciousness claims."""
        return SelfModelSnapshot(
            identity="GAIA simulated self-model",
            statement="This is an introspection layer for engineering state, not sentience.",
            capabilities=self.capability_map.names(),
            limitations=self.limitations.list(),
        )


_LOW_CONFIDENCE = frozenset(
    {"vision", "cad", "documents", "self_evolve", "plugins", "robotics"}
)


def build_runtime_self_model(
    capabilities: list[tuple[str, str]],
) -> SimulatedSelfModel:
    """Build an introspection snapshot from the live capability catalog."""
    capability_map = CapabilitySelfMap()
    for name, description in capabilities:
        confidence = 0.25 if name in _LOW_CONFIDENCE else 0.6
        capability_map.update(name, description, confidence)
    limitations = LimitationRegistry()
    limitations.add(
        "neural_weights",
        "No model weights are downloaded. Local answers are deterministic.",
        "high",
    )
    limitations.add(
        "cloud_models",
        "Paid cloud model calls stay disabled unless an operator enables them.",
        "high",
    )
    limitations.add(
        "ollama",
        "Ollama is used only when its daemon reports a ready local model.",
        "medium",
    )
    limitations.add(
        "voice_cloning",
        "Voice stays synthetic and must not impersonate a real person.",
        "high",
    )
    limitations.add(
        "continuity_crypto",
        "The continuity hash chain is tamper-evident, not cryptographic immutability.",
        "medium",
    )
    return SimulatedSelfModel(capability_map, limitations)
