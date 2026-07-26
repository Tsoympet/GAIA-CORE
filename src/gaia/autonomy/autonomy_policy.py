"""GAIA autonomy policy."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AutonomyPolicy(BaseModel):
    """Safe engineering simulation component for autonomy policy."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
