"""GAIA goal manager."""
from __future__ import annotations
from pydantic import BaseModel, Field

class GoalManager(BaseModel):
    """Safe engineering simulation component for goal manager."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
