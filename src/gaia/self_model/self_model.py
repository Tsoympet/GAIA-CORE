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
