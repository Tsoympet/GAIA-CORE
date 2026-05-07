"""Limitation tracking for GAIA's simulated self-model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Limitation(BaseModel):
    """Known limitation of the current GAIA implementation."""

    name: str
    description: str
    severity: str = "medium"


class LimitationRegistry(BaseModel):
    """Registry of explicit implementation limitations."""

    limitations: dict[str, Limitation] = Field(default_factory=dict)

    def add(self, name: str, description: str, severity: str = "medium") -> Limitation:
        """Add a limitation record."""
        limitation = Limitation(name=name, description=description, severity=severity)
        self.limitations[name] = limitation
        return limitation

    def list(self) -> list[Limitation]:
        """List limitations in stable order."""
        return [self.limitations[name] for name in sorted(self.limitations)]
