"""Caller-supplied session identity survives a continuity restart."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from gaia.continuity.schema import MIGRATION_V1
from gaia.continuity.store import ContinuityStore
from gaia.core.runtime import TaskRequest, create_runtime
from gaia.core.session import Session, SessionManager
from gaia.security.field_cipher import FieldCipher


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


def test_restart_restores_workspace_and_redacts_session_metadata(tmp_path: Path) -> None:
    journal = tmp_path / "continuity.sqlite3"
    runtime = create_runtime(continuity_path=journal)
    created = asyncio.run(
        runtime.sessions.create_session(
            "ada",
            workspace_id="ws-1",
            metadata={"topic": "kept", "approval_token": "sekret"},
        )
    )
    asyncio.run(
        runtime.submit_task(TaskRequest(task="Remember this workspace", session_id=created.id))
    )
    assert created.metadata["approval_token"] == "[redacted]"
    assert created.metadata["topic"] == "kept"

    restored = create_runtime(continuity_path=journal)
    session = restored.sessions.get(created.id)
    assert session is not None
    assert session.user_id == "ada"
    assert session.workspace_id == "ws-1"
    assert session.metadata["topic"] == "kept"
    assert session.metadata["approval_token"] == "[redacted]"
    assert session.created_at == created.created_at


def test_schema_v1_session_row_upgrades_without_dropping_identity(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(MIGRATION_V1)
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (1, 'continuity_initial', '2026-01-01T00:00:00+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO sessions (session_id, user_id, created_at)
            VALUES ('legacy', 'ada', '2026-01-02T00:00:00+00:00')
            """
        )

    store = ContinuityStore(path)
    assert store.schema_version() == 3
    loaded = store.list_sessions()
    assert len(loaded) == 1
    assert loaded[0].id == "legacy"
    assert loaded[0].user_id == "ada"
    assert loaded[0].workspace_id is None
    assert loaded[0].metadata == {}
    assert store.rollback_schema(1) == 1
    with sqlite3.connect(path) as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(sessions)")}
    assert "metadata_json" not in columns
    assert "workspace_id" not in columns
    upgraded = ContinuityStore(path)
    assert upgraded.schema_version() == 3
    assert upgraded.list_sessions()[0].user_id == "ada"


def test_checkpoint_rollback_restores_session_metadata(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    original = Session(
        id="s-roll",
        user_id="ada",
        workspace_id="ws-a",
        metadata={"topic": "baseline"},
    )
    store.upsert_session(original)
    checkpoint = store.publish_checkpoint(reason="sessions", kernel_id="test")
    replacement = original.model_copy(deep=True)
    replacement.workspace_id = "ws-b"
    replacement.metadata = {"topic": "later"}
    store.upsert_session(replacement)

    store.rollback_to(checkpoint.checkpoint_id)
    loaded = store.list_sessions()
    assert len(loaded) == 1
    assert loaded[0].workspace_id == "ws-a"
    assert loaded[0].metadata["topic"] == "baseline"


def test_old_checkpoint_without_sessions_does_not_erase_them(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    store.upsert_session(Session(id="s-keep", user_id="ada", workspace_id="ws-live"))
    original_snapshot = store._snapshot_on

    def snapshot_without_sessions(connection: sqlite3.Connection) -> dict[str, object]:
        payload = original_snapshot(connection)
        payload.pop("sessions", None)
        return payload

    store._snapshot_on = snapshot_without_sessions  # type: ignore[method-assign]
    checkpoint = store.publish_checkpoint(reason="legacy-shape", kernel_id="test")
    del store._snapshot_on
    store.upsert_session(
        Session(id="s-keep", user_id="ada", workspace_id="ws-live", metadata={"topic": "after"})
    )
    store.rollback_to(checkpoint.checkpoint_id)
    loaded = store.list_sessions()
    assert loaded[0].workspace_id == "ws-live"
    assert loaded[0].metadata["topic"] == "after"


def test_recovery_redacts_injected_session_metadata(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    store.upsert_session(Session(id="s-inject", user_id="ada", metadata={"topic": "kept"}))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET metadata_json = ? WHERE session_id = ?",
            ('{"topic": "kept", "approval_token": "restored-secret"}', "s-inject"),
        )
    ContinuityStore(path).recover()
    loaded = ContinuityStore(path).list_sessions()[0]
    assert loaded.metadata["topic"] == "kept"
    assert loaded.metadata["approval_token"] == "[redacted]"


def test_session_metadata_is_sealed_when_a_data_key_is_set(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    store.upsert_session(
        Session(id="s-seal", user_id="ada", metadata={"topic": "visible-session-note"})
    )
    cipher = FieldCipher(b"\x03" * 32)
    sealed = ContinuityStore(path, cipher=cipher)
    assert b"visible-session-note" not in path.read_bytes()
    loaded = sealed.list_sessions()
    assert loaded[0].metadata["topic"] == "visible-session-note"
