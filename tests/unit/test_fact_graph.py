"""Symbolic facts, consent, and deletion requests survive a new process."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from gaia.memory import DeletionRequestStatus, MemoryConsent, MemoryManager, MemoryScope
from gaia.memory.sqlite_graph import SQLiteFactGraph


def test_fact_graph_reloads_facts_consent_and_deletions(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    memory = MemoryManager(fact_graph=SQLiteFactGraph(db_path))
    fact = memory.add_fact(
        "quartz",
        "stores",
        "bearing-note",
        confidence=0.4,
        owner_id="local",
    )
    memory.revoke_consent("local")
    request = memory.request_deletion("local", MemoryScope.PROJECT, "stale bench note")
    reviewed = memory.review_deletion_request(request.request_id, approve=False)

    assert memory.status().fact_store == "sqlite-facts"
    assert memory.status().fact_store_durable is True

    reopened = MemoryManager(fact_graph=SQLiteFactGraph(db_path))

    loaded_facts = reopened.list_facts()
    assert [item.fact_id for item in loaded_facts] == [fact.fact_id]
    assert loaded_facts[0].confidence == 0.4
    assert loaded_facts[0].owner_id == "local"
    assert reopened.consent["local"] is MemoryConsent.REVOKED
    loaded = reopened.deletion_requests[reviewed.request_id]
    assert loaded.status is DeletionRequestStatus.DENIED
    assert loaded.reviewed_at is not None
    assert reopened.status().pending_deletion_requests == 0


def test_process_memory_is_not_a_durable_fact_store() -> None:
    status = MemoryManager().status()

    assert status.fact_store == "process"
    assert status.fact_store_durable is False


def test_revoked_consent_does_not_store_a_fact(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    memory = MemoryManager(fact_graph=SQLiteFactGraph(db_path))
    kept = memory.add_fact("quartz", "stores", "public", owner_id="ada")
    memory.revoke_consent("local")

    with pytest.raises(PermissionError, match="memory consent revoked for owner: local"):
        memory.add_fact("quartz", "stores", "secret", owner_id="local")

    assert [fact.fact_id for fact in memory.list_facts()] == [kept.fact_id]
    assert _fact_count(db_path) == 1
    reopened = MemoryManager(fact_graph=SQLiteFactGraph(db_path))
    assert [fact.object for fact in reopened.list_facts()] == ["public"]
    with pytest.raises(PermissionError, match="memory consent revoked for owner: local"):
        reopened.add_fact("quartz", "stores", "secret", owner_id="local")
    assert _fact_count(db_path) == 1


def test_unknown_and_granted_consent_reload_owner_in_a_second_process(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    memory = MemoryManager(fact_graph=SQLiteFactGraph(db_path))
    unknown = memory.add_fact("quartz", "stores", "note", confidence=0.4, owner_id="local")
    memory.grant_consent("ada")
    granted = memory.add_fact("ada", "prefers", "quartz", owner_id="ada")

    script = "\n".join(
        [
            "from gaia.memory import MemoryConsent, MemoryManager",
            "from gaia.memory.sqlite_graph import SQLiteFactGraph",
            f"memory = MemoryManager(fact_graph=SQLiteFactGraph({str(db_path)!r}))",
            "facts = {fact.fact_id: fact for fact in memory.list_facts()}",
            f"assert facts[{unknown.fact_id!r}].owner_id == 'local'",
            f"assert facts[{unknown.fact_id!r}].confidence == 0.4",
            f"assert facts[{granted.fact_id!r}].owner_id == 'ada'",
            "assert memory.consent['ada'] is MemoryConsent.GRANTED",
            "assert 'local' not in memory.consent",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_legacy_fact_rows_without_owner_still_load(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE symbolic_facts (
                fact_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                confidence REAL NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO symbolic_facts (
                fact_id, subject, predicate, object, confidence,
                metadata_json, created_at
            ) VALUES ('old-fact', 'quartz', 'stores', 'legacy', 0.2, '{}',
                      '2026-01-01T00:00:00+00:00')
            """
        )

    memory = MemoryManager(fact_graph=SQLiteFactGraph(db_path))
    loaded = memory.list_facts()
    assert [fact.fact_id for fact in loaded] == ["old-fact"]
    assert loaded[0].owner_id is None

    added = memory.add_fact("quartz", "stores", "new", owner_id="local")
    reopened = MemoryManager(fact_graph=SQLiteFactGraph(db_path))
    by_id = {fact.fact_id: fact.owner_id for fact in reopened.list_facts()}
    assert by_id["old-fact"] is None
    assert by_id[added.fact_id] == "local"


def _fact_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM symbolic_facts").fetchone()
    assert row is not None
    return int(row[0])
