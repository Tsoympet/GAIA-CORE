"""Fact-graph API rows survive a new application process."""

import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from gaia.server.app import create_app


def test_fact_routes_reload_from_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    first = TestClient(create_app(fact_db=db_path))

    created = first.post(
        "/memory/facts",
        json={
            "subject": "quartz",
            "predicate": "stores",
            "object_value": "bearing-note",
            "confidence": 0.4,
            "owner_id": "local",
        },
    )
    assert created.status_code == 200
    fact_id = created.json()["fact_id"]
    assert created.json()["owner_id"] == "local"
    assert created.json()["score_calibrated"] is False
    assert first.post("/memory/consent/revoke", json={"owner_id": "local"}).status_code == 200
    deletion = first.post(
        "/memory/deletion-requests",
        json={"owner_id": "local", "scope": "project", "reason": "stale bench note"},
    )
    assert deletion.status_code == 200
    request_id = deletion.json()["request_id"]

    restarted = TestClient(create_app(fact_db=db_path))
    facts = restarted.get("/memory/facts")
    assert facts.status_code == 200
    assert facts.json()[0]["fact_id"] == fact_id
    assert facts.json()[0]["confidence"] == 0.4
    assert facts.json()[0]["owner_id"] == "local"
    assert facts.json()[0]["score_calibrated"] is False
    status = restarted.get("/memory/status")
    assert status.status_code == 200
    body = status.json()
    assert body["fact_store"] == "sqlite-facts"
    assert body["fact_store_durable"] is True
    assert body["consent_records"]["local"] == "revoked"
    assert body["pending_deletion_requests"] == 1
    blocked = restarted.post(
        "/memory",
        json={"owner_id": "local", "scope": "project", "content": "new note"},
    )
    assert blocked.status_code == 403
    blocked_fact = restarted.post(
        "/memory/facts",
        json={
            "subject": "quartz",
            "predicate": "stores",
            "object_value": "after-revoke",
            "owner_id": "local",
        },
    )
    assert blocked_fact.status_code == 403
    assert blocked_fact.json()["detail"] == "memory consent revoked for owner: local"
    assert _fact_count(db_path) == 1
    assert [item["fact_id"] for item in restarted.get("/memory/facts").json()] == [fact_id]
    reviewed = restarted.post(
        f"/memory/deletion-requests/{request_id}/review",
        json={"approve": False},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "denied"


def test_revoked_consent_rejects_fact_write_before_insert(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    client = TestClient(create_app(fact_db=db_path))
    assert client.post("/memory/consent/revoke", json={"owner_id": "local"}).status_code == 200

    blocked = client.post(
        "/memory/facts",
        json={
            "subject": "quartz",
            "predicate": "stores",
            "object_value": "secret",
            "confidence": 0.4,
            "owner_id": "local",
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "memory consent revoked for owner: local"
    assert client.get("/memory/facts").json() == []
    assert _fact_count(db_path) == 0

    omitted = client.post(
        "/memory/facts",
        json={"subject": "quartz", "predicate": "stores", "object_value": "as-default"},
    )
    assert omitted.status_code == 200
    assert omitted.json()["owner_id"] == "default"
    assert _fact_count(db_path) == 1

    client.post("/memory/consent/revoke", json={"owner_id": "default"})
    sneaky = client.post(
        "/memory/facts",
        json={"subject": "quartz", "predicate": "stores", "object_value": "omitted"},
    )
    assert sneaky.status_code == 403
    assert sneaky.json()["detail"] == "memory consent revoked for owner: default"
    assert _fact_count(db_path) == 1

    missing = client.post(
        "/memory/facts",
        json={
            "subject": "quartz",
            "predicate": "stores",
            "object_value": "unowned",
            "owner_id": None,
        },
    )
    assert missing.status_code == 422
    assert _fact_count(db_path) == 1


def test_granted_fact_owner_reloads_in_a_second_process(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.sqlite3"
    client = TestClient(create_app(fact_db=db_path))
    assert client.post("/memory/consent/grant", json={"owner_id": "ada"}).status_code == 200
    created = client.post(
        "/memory/facts",
        json={
            "subject": "ada",
            "predicate": "prefers",
            "object_value": "quartz",
            "owner_id": "ada",
        },
    )
    assert created.status_code == 200
    fact_id = created.json()["fact_id"]
    assert created.json()["score_calibrated"] is False

    script = "\n".join(
        [
            "from fastapi.testclient import TestClient",
            "from gaia.server.app import create_app",
            f"client = TestClient(create_app(fact_db={str(db_path)!r}))",
            "facts = client.get('/memory/facts').json()",
            "assert len(facts) == 1",
            f"assert facts[0]['fact_id'] == {fact_id!r}",
            "assert facts[0]['owner_id'] == 'ada'",
            "assert facts[0]['score_calibrated'] is False",
            "status = client.get('/memory/status').json()",
            "assert status['consent_records']['ada'] == 'granted'",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_legacy_fact_without_owner_loads_through_the_api(tmp_path: Path) -> None:
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

    client = TestClient(create_app(fact_db=db_path))
    facts = client.get("/memory/facts")
    assert facts.status_code == 200
    assert facts.json()[0]["fact_id"] == "old-fact"
    assert facts.json()[0]["owner_id"] is None
    assert facts.json()[0]["score_calibrated"] is False


def _fact_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM symbolic_facts").fetchone()
    assert row is not None
    return int(row[0])
