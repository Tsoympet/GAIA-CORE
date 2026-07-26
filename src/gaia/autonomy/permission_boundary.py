"""GAIA permission boundary."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PermissionBoundary(BaseModel):
    """Safe engineering simulation component for permission boundary."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
