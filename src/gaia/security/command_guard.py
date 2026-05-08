"""GAIA command guard."""
from __future__ import annotations
from pydantic import BaseModel, Field

class CommandGuard(BaseModel):
    """Safe engineering simulation component for command guard."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
