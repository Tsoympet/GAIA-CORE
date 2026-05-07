"""Bootstrap memory store.

This in-memory implementation is intentionally simple, but exposes async hooks
that can be backed by encrypted local storage, symbolic stores, and vector
indexes as the platform matures.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryEvent(BaseModel):
    """Auditable event captured by the memory subsystem."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryStore(BaseModel):
    """Async memory hook surface."""

    events: list[MemoryEvent] = Field(default_factory=list)

    async def record_event(self, event_type: str, payload: dict[str, Any]) -> MemoryEvent:
        """Record a memory event and return its descriptor."""
        event = MemoryEvent(event_type=event_type, payload=payload)
        self.events.append(event)
        return event


def create_memory_store() -> MemoryStore:
    """Create the bootstrap memory store."""
    return MemoryStore()
