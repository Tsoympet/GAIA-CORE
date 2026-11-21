"""Symbolic facts, consent, and deletion requests survive a new process."""

from pathlib import Path

from gaia.memory import DeletionRequestStatus, MemoryConsent, MemoryManager, MemoryScope
from gaia.memory.sqlite_graph import SQLiteFactGraph


def test_fact_graph_reloads_facts_consent_and_deletions(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    memory = MemoryManager(fact_graph=SQLiteFactGraph(db_path))
    fact = memory.add_fact("quartz", "stores", "bearing-note", confidence=0.4)
    memory.revoke_consent("local")
    request = memory.request_deletion("local", MemoryScope.PROJECT, "stale bench note")
    reviewed = memory.review_deletion_request(request.request_id, approve=False)

    assert memory.status().fact_store == "sqlite-facts"
    assert memory.status().fact_store_durable is True

    reopened = MemoryManager(fact_graph=SQLiteFactGraph(db_path))

    loaded_facts = reopened.list_facts()
    assert [item.fact_id for item in loaded_facts] == [fact.fact_id]
    assert loaded_facts[0].confidence == 0.4
    assert reopened.consent["local"] is MemoryConsent.REVOKED
    loaded = reopened.deletion_requests[reviewed.request_id]
    assert loaded.status is DeletionRequestStatus.DENIED
    assert loaded.reviewed_at is not None
    assert reopened.status().pending_deletion_requests == 0


def test_process_memory_is_not_a_durable_fact_store() -> None:
    status = MemoryManager().status()

    assert status.fact_store == "process"
    assert status.fact_store_durable is False
