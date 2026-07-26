"""GAIA self consistency checks."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SelfConsistencyChecker(BaseModel):
    """Safe engineering simulation component for self consistency checks."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
