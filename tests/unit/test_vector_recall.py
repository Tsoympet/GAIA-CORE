"""Scoped recall uses the local vector index and keeps symbolic facts."""

from pathlib import Path

from gaia.memory import MemoryManager, MemoryScope
from gaia.memory.indexer import (
    SCORE_NOTE,
    SCORES_CALIBRATED,
    SQLITE_SCORE_NOTE,
    SQLITE_VECTOR_INDEX,
    VECTOR_INDEX,
)
from gaia.memory.sqlite_index import SQLiteVectorIndex
from gaia.memory.symbolic import fact_owner


def test_recall_ranks_the_vector_index_and_skips_unrelated_notes() -> None:
    memory = MemoryManager()
    memory.remember("Pump curve at 50 hertz", MemoryScope.PROJECT, "local")
    memory.remember("Kitchen inventory for spare bolts", MemoryScope.PROJECT, "local")
    memory.remember("Pump curve for the other owner", MemoryScope.PROJECT, "other")

    matches = memory.recall("pump curve", "local")

    assert [record.content for record, _score in matches] == ["Pump curve at 50 hertz"]
    assert matches[0][1] > 0.2
    assert memory.status().vector_index == VECTOR_INDEX
    assert memory.status().scores_calibrated is SCORES_CALIBRATED
    assert "uncalibrated" in memory.status().score_note
    assert memory.status().score_note == SCORE_NOTE


def test_symbolic_facts_stay_on_the_graph_and_rank_separately() -> None:
    memory = MemoryManager()
    memory.remember("Workspace note about fasteners", MemoryScope.PROJECT, "local")
    fact = memory.add_fact(
        "bearing",
        "prefers",
        "local-notes",
        confidence=0.4,
        owner_id="local",
    )
    memory.add_fact("secret", "belongs-to", "other-owner", owner_id="other")

    facts = memory.match_facts("bearing prefers local-notes", "local")

    assert memory.symbolic.facts[fact.fact_id] is fact
    assert memory.status().indexed_documents == 1
    assert [item.fact_id for item, _score in facts] == [fact.fact_id]
    assert facts[0][1] > 0.2
    assert memory.match_facts("secret belongs-to", "local") == []


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
    memory.add_fact("bearing", "prefers", "local-notes", owner_id="local")
    stored_embedding = list(memory.vector_store.documents[kept.record_id].embedding)
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
    assert reopened.get_record(dropped.record_id) is None
    assert reopened.list_facts("local") == []
    status = reopened.status()
    assert status.vector_index == SQLITE_VECTOR_INDEX
    assert status.scores_calibrated is False
    assert status.score_note == SQLITE_SCORE_NOTE
    assert "uncalibrated" in status.score_note


def test_unowned_symbolic_fact_is_hidden_from_every_owner() -> None:
    memory = MemoryManager()
    unowned = memory.add_fact("secret", "visible-to", "everyone")
    owned = memory.add_fact("bearing", "prefers", "local-notes", owner_id="local")

    assert fact_owner(unowned) is None
    assert [fact.fact_id for fact in memory.list_facts("local")] == [owned.fact_id]
    assert memory.list_facts("other") == []
    assert memory.list_facts(" ") == []
    assert memory.match_facts("secret visible-to everyone", "local") == []
    assert memory.match_facts("secret visible-to everyone", "other") == []
    assert unowned.fact_id in {fact.fact_id for fact in memory.list_facts(None)}
