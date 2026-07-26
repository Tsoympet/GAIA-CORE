"""Scoped memory containers for project, user, session, and timeline views."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MemoryScope(StrEnum):
    PROJECT = "project"
    USER = "user"
    SESSION = "session"
    TIMELINE = "timeline"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    content: str
    scope: MemoryScope
    owner_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    record_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ScopedMemory:
    scope: MemoryScope
    records: dict[str, MemoryRecord] = field(default_factory=dict)

    def add(
        self,
        content: str,
        owner_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            content=content,
            scope=self.scope,
            owner_id=owner_id,
            metadata=metadata or {},
        )
        self.records[record.record_id] = record
        return record

    def list_for_owner(self, owner_id: str) -> list[MemoryRecord]:
        return [
            record
            for record in self.records.values()
            if record.owner_id == owner_id
        ]
