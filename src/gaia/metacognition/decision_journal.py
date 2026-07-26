"""GAIA decision journal."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DecisionJournal(BaseModel):
    """Safe engineering simulation component for decision journal."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
