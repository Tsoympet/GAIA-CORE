"""GAIA uncertainty tracker."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UncertaintyTracker(BaseModel):
    """Safe engineering simulation component for uncertainty tracker."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
