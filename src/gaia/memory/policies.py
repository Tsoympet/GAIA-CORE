"""Memory retention and indexing policies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .scoped import MemoryRecord


@dataclass(frozen=True, slots=True)
class MemoryPolicy:
    retention_days: int | None = None
    min_importance: float = 0.0
    index_by_default: bool = True

    def should_keep(self, record: MemoryRecord) -> bool:
        importance = float(record.metadata.get("importance", 1.0))
        if importance < self.min_importance:
            return False
        if self.retention_days is None:
            return True
        return record.created_at >= datetime.now(UTC) - timedelta(days=self.retention_days)

    def should_index(self, record: MemoryRecord) -> bool:
        return bool(record.metadata.get("index", self.index_by_default)) and self.should_keep(record)
