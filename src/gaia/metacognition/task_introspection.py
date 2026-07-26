"""GAIA task introspection."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskIntrospection(BaseModel):
    """Safe engineering simulation component for task introspection."""
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)

    def record(self, note: str) -> None:
        self.notes.append(note)
