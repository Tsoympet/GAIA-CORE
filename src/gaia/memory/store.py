"""Compatibility memory store backed by the GAIA memory manager."""

from __future__ import annotations

from typing import Any

from gaia.memory.memory_manager import MemoryManager, MemoryRecord


class MemoryStore(MemoryManager):
    """Async memory hook surface for orchestration events."""

    async def record_event(self, event_type: str, payload: dict[str, Any]) -> MemoryRecord:
        """Record an auditable runtime event."""
        return await self.remember(event_type, event_type, payload)


def create_memory_store() -> MemoryStore:
    """Create the bootstrap memory store."""
    return MemoryStore()
