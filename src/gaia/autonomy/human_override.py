"""GAIA human override."""
from __future__ import annotations
from pydantic import BaseModel, Field

class HumanOverride(BaseModel):
    """Safe engineering simulation component for human override."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
