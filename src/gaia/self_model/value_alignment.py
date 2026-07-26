"""GAIA value alignment constraints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValueAlignment(BaseModel):
    """Safe engineering simulation component for value alignment constraints."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
