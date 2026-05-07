"""Simulated capability self-map for GAIA introspection."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CapabilityEntry(BaseModel):
    """A self-reported capability and confidence estimate."""

    name: str
    description: str
    confidence: float = 0.5


class CapabilitySelfMap(BaseModel):
    """Safe engineering simulation of GAIA capability awareness."""

    capabilities: dict[str, CapabilityEntry] = Field(default_factory=dict)

    def update(self, name: str, description: str, confidence: float) -> CapabilityEntry:
        """Record or update a simulated capability entry."""
        entry = CapabilityEntry(
            name=name,
            description=description,
            confidence=max(0.0, min(1.0, confidence)),
        )
        self.capabilities[name] = entry
        return entry

    def names(self) -> list[str]:
        """Return known capability names."""
        return sorted(self.capabilities)
