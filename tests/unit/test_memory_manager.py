import pytest

from gaia.memory.memory_manager import MemoryManager


@pytest.mark.asyncio
async def test_memory_manager_remembers_and_searches() -> None:
    memory = MemoryManager()
    await memory.remember("note", "local-first runtime note")

    results = await memory.search("runtime")

    assert len(results) == 1
    assert results[0].kind == "note"
