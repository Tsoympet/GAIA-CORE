"""Continuity checkpoints are cited as evidence digests, not payload copies."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from gaia.continuity.store import ContinuityStore
from gaia.core.runtime import TaskRequest, create_runtime
from gaia.kernel.goal_manager import Goal
from gaia.organism.binding import CHECKPOINT_ORIGIN
from gaia.organism.organism import MemoryOrganism


def test_checkpoint_evidence_omits_payload_and_is_idempotent(tmp_path: Path) -> None:
    journal = tmp_path / "continuity.sqlite3"
    organism_path = tmp_path / "organism.sqlite3"
    store = ContinuityStore(journal)
    goal = Goal(
        objective="Move token=super-secret ballast",
        session_id="session-bind",
        metadata={"approval_token": "do-not-copy"},
    )
    store.upsert_goal(goal)
    published = store.publish_checkpoint(reason="operator", kernel_id="kernel-1")
    payload = store.get_checkpoint(published.checkpoint_id)
    assert payload is not None
    assert payload.payload_json is not None
    assert "super-secret" in payload.payload_json

    organism = MemoryOrganism(organism_path)
    added = organism.bind_continuity(store)
    assert added == 1
    assert organism.bind_continuity(store) == 0

    citations = [
        record
        for record in organism.evidence.list_records()
        if record.origin == CHECKPOINT_ORIGIN
    ]
    assert len(citations) == 1
    body = citations[0].content_text or ""
    parsed = json.loads(body)
    assert parsed["checkpoint_id"] == published.checkpoint_id
    assert parsed["payload_sha256"] == published.payload_sha256
    assert "payload_json" not in parsed
    assert "super-secret" not in body
    assert "do-not-copy" not in body
    assert "ballast" not in body
    assert citations[0].relationship == "checkpoint-digest"

    again = store.publish_checkpoint(reason="verified_run", kernel_id="kernel-1")
    citations = [
        record
        for record in organism.evidence.list_records()
        if record.origin == CHECKPOINT_ORIGIN
    ]
    assert {record.execution_id for record in citations} == {
        published.checkpoint_id,
        again.checkpoint_id,
    }
    assert organism.evidence.verify_chain() is True


def test_runtime_binds_checkpoint_digests_when_both_stores_exist(tmp_path: Path) -> None:
    runtime = create_runtime(
        continuity_path=tmp_path / "continuity.sqlite3",
        organism_path=tmp_path / "organism.sqlite3",
    )
    assert runtime.organism is not None
    assert runtime.organism.continuity_bound is True
    asyncio.run(
        runtime.submit_task(
            TaskRequest(task="Inspect token=super-secret locally", session_id="s1")
        )
    )
    citations = [
        record
        for record in runtime.organism.evidence.list_records()
        if record.origin == CHECKPOINT_ORIGIN
    ]
    assert citations
    joined = " ".join(record.content_text or "" for record in citations)
    assert "super-secret" not in joined
    assert "Inspect" not in joined
    assert all(record.relationship == "checkpoint-digest" for record in citations)
