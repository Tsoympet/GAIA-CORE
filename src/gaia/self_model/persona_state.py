"""GAIA persona configuration."""
from __future__ import annotations
from pydantic import BaseModel, Field

class PersonaState(BaseModel):
    """Safe engineering simulation component for persona configuration."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
