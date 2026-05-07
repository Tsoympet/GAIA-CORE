"""Memory consolidation for safe idle cognition."""

from __future__ import annotations

from gaia.memory.memory_manager import MemoryManager, MemoryRecord


class MemoryConsolidator:
    """Summarizes recent memory into safe internal notes."""

    async def consolidate(self, memory: MemoryManager) -> MemoryRecord:
        """Write a safe internal consolidation note."""
        summary = f"Consolidated {len(memory.records)} memory records for future planning."
        return await memory.remember("idle_consolidation", summary, {"source": "dreaming"})
