"""Scoped recall keeps hashed n-gram vectors in the local SQLite index."""

from pathlib import Path

from fastapi.testclient import TestClient

from gaia.memory import MemoryManager, MemoryScope
from gaia.memory.indexer import (
    MIN_VECTOR_SCORE,
    SCORES_CALIBRATED,
    SQLITE_SCORE_NOTE,
    SQLITE_VECTOR_INDEX,
    simple_embedding,
)
from gaia.memory.sqlite_index import SQLiteVectorIndex
from gaia.server.app import create_app


def test_scoped_vector_recall_survives_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "phase4.sqlite3"
    memory = MemoryManager(vector_store=SQLiteVectorIndex(db_path))
    kept = memory.remember("Pump curve at 50 hertz", MemoryScope.PROJECT, "local")
    dropped = memory.remember(
        "Kitchen inventory for spare bolts",
        MemoryScope.SESSION,
        "local",
    )
    memory.remember("Pump curve for the other owner", MemoryScope.PROJECT, "other")
    memory.add_fact("bearing", "prefers", "local-notes")
    memory.revoke_consent("local")
    stored_embedding = list(memory.vector_store.documents[kept.record_id].embedding)
    assert stored_embedding == simple_embedding(kept.content)
    removal = memory.request_deletion("local", MemoryScope.SESSION, "drop the kitchen note")
    memory.review_deletion_request(removal.request_id, approve=True)
    assert isinstance(memory.vector_store, SQLiteVectorIndex)
    memory.vector_store.close()

    reopened = MemoryManager(vector_store=SQLiteVectorIndex(db_path))
    matches = reopened.recall("pump curve", "local")

    assert [record.record_id for record, _score in matches] == [kept.record_id]
    assert matches[0][0].content == "Pump curve at 50 hertz"
    assert matches[0][1] > 0.2
    assert reopened.vector_store.documents[kept.record_id].embedding == stored_embedding
    assert dropped.record_id not in reopened.vector_store.documents
    assert reopened.vector_store.records.get(dropped.record_id) is None
    assert reopened.symbolic.facts == {}
    assert reopened.consent == {}
    status = reopened.status()
    assert status.vector_index == SQLITE_VECTOR_INDEX
    assert status.scores_calibrated is SCORES_CALIBRATED
    assert status.scores_calibrated is False
    assert status.score_note == SQLITE_SCORE_NOTE
    assert "uncalibrated" in status.score_note
    assert status.durable is True


def test_exact_non_ascii_query_recalls_stored_note(tmp_path: Path) -> None:
    note = "άντληση καμπύλης"
    app = create_app(phase4_db=tmp_path / "unicode.sqlite3")
    client = TestClient(app)
    written = client.post(
        "/memory",
        json={"content": note, "scope": "project", "owner_id": "local"},
    )

    assert written.status_code == 200
    record_id = written.json()["record_id"]
    embedding = list(app.state.services.memory.vector_store.documents[record_id].embedding)
    assert embedding == simple_embedding(note)
    assert any(value != 0.0 for value in embedding)

    recalled = client.post(
        "/memory/recall",
        json={"query": note, "owner_id": "local"},
    )

    assert recalled.status_code == 200
    hits = recalled.json()
    assert [hit["record_id"] for hit in hits] == [record_id]
    assert hits[0]["content"] == note
    assert hits[0]["score"] > MIN_VECTOR_SCORE
    assert hits[0]["score_calibrated"] is False
    assert hits[0]["score_calibrated"] is SCORES_CALIBRATED
