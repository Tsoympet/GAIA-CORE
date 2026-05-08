"""GAIA internal imagination sandbox."""
from __future__ import annotations
from pydantic import BaseModel, Field

class ImaginationSandbox(BaseModel):
    """Safe engineering simulation component for internal imagination sandbox."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
