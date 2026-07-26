"""GAIA rollback manager."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RollbackManager(BaseModel):
    """Safe engineering simulation component for rollback manager."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
