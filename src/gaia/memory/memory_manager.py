"""Safe in-memory manager for GAIA memory events and notes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """A lightweight memory record for local-first bootstrap storage."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        """Backward-compatible event type alias."""
        return self.kind

    @property
    def payload(self) -> dict[str, Any]:
        """Backward-compatible payload alias."""
        return self.metadata


class MemoryManager:
    """Append-only memory facade used by runtime, metacognition, and dreaming."""

    def __init__(self) -> None:
        self.records: list[MemoryRecord] = []

    async def remember(
        self, kind: str, content: str, metadata: dict[str, Any] | None = None
    ) -> MemoryRecord:
        """Store a safe internal memory record."""
        record = MemoryRecord(kind=kind, content=content, metadata=metadata or {})
        self.records.append(record)
        return record

    async def search(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Return simple substring matches for the bootstrap implementation."""
        lowered = query.lower()
        matches = [record for record in self.records if lowered in record.content.lower()]
        return matches[:limit]

    @property
    def events(self) -> list[MemoryRecord]:
        """Backward-compatible event accessor."""
        return self.records
