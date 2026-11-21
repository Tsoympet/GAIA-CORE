"""Fact-graph API rows survive a new application process."""

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
        },
    )
    assert created.status_code == 200
    fact_id = created.json()["fact_id"]
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
    reviewed = restarted.post(
        f"/memory/deletion-requests/{request_id}/review",
        json={"approve": False},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "denied"
