"""GAIA creative association."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreativeAssociation(BaseModel):
    """Safe engineering simulation component for creative association."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
