"""GAIA autonomy manager."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AutonomyManager(BaseModel):
    """Safe engineering simulation component for autonomy manager."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
