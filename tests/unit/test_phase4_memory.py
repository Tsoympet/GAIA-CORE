import pytest

from gaia.memory import DeletionRequestStatus, MemoryConsent, MemoryManager, MemoryScope


def test_phase4_memory_status_tracks_scopes_indexes_and_consent() -> None:
    memory = MemoryManager()
    memory.grant_consent("workspace-1")

    record = memory.remember(
        "GAIA should remember phase four workspace context",
        MemoryScope.PROJECT,
        "workspace-1",
        metadata={"importance": 0.9},
    )
    memory.add_fact("GAIA", "phase", "4", confidence=0.8)
    status = memory.status()

    assert record.record_id
    assert status.scopes["project"] == 1
    assert status.indexed_documents == 1
    assert status.symbolic_facts == 1
    assert status.consent_records["workspace-1"] == MemoryConsent.GRANTED.value
    assert status.local_first is True


def test_phase4_memory_deletion_requires_review_before_removal() -> None:
    memory = MemoryManager()
    memory.remember("temporary workspace memory", MemoryScope.SESSION, "session-1")

    request = memory.request_deletion(
        "session-1",
        MemoryScope.SESSION,
        "user requested cleanup",
    )

    assert memory.status().pending_deletion_requests == 1
    assert len(memory.list_scope(MemoryScope.SESSION, "session-1")) == 1

    reviewed = memory.review_deletion_request(request.request_id, approve=True)

    assert reviewed.status == DeletionRequestStatus.APPROVED
    assert memory.status().pending_deletion_requests == 0
    assert memory.list_scope(MemoryScope.SESSION, "session-1") == []


def test_phase4_memory_revoked_consent_blocks_new_writes() -> None:
    memory = MemoryManager()
    memory.revoke_consent("user-1")

    with pytest.raises(PermissionError, match="memory consent revoked"):
        memory.remember("do not store", MemoryScope.USER, "user-1")
