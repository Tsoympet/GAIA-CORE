"""GAIA action review."""
from __future__ import annotations
from pydantic import BaseModel, Field

class ActionReview(BaseModel):
    """Safe engineering simulation component for action review."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
