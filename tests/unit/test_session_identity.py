"""Caller-supplied session ids survive a continuity restart."""

from __future__ import annotations

import asyncio
from pathlib import Path

from gaia.core.runtime import TaskRequest, create_runtime
from gaia.core.session import SessionManager


def test_explicit_session_id_is_adopted() -> None:
    manager = SessionManager()
    first = asyncio.run(manager.get_or_create("s1"))
    second = asyncio.run(manager.get_or_create("s1"))
    minted = asyncio.run(manager.get_or_create(None))
    assert first.id == "s1"
    assert second.id == "s1"
    assert minted.id != "s1"


def test_restart_restores_the_session_id(tmp_path: Path) -> None:
    journal = tmp_path / "continuity.sqlite3"
    organism = tmp_path / "organism.sqlite3"
    runtime = create_runtime(continuity_path=journal, organism_path=organism)
    asyncio.run(
        runtime.submit_task(TaskRequest(task="Remember this local session", session_id="s1"))
    )
    assert runtime.sessions.get("s1") is not None
    assert runtime.organism is not None
    assert runtime.organism.export_owner("s1")["memories"]

    restored = create_runtime(continuity_path=journal, organism_path=organism)
    session = restored.sessions.get("s1")
    assert session is not None
    assert session.id == "s1"
    assert restored.organism is not None
    assert restored.organism.export_owner("s1")["memories"]
