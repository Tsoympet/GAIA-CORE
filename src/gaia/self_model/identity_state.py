"""GAIA simulated identity state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IdentityState(BaseModel):
    """Safe engineering simulation component for simulated identity state."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
