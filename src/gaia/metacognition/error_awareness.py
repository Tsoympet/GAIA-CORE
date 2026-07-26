"""GAIA error awareness."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorAwareness(BaseModel):
    """Safe engineering simulation component for error awareness."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
