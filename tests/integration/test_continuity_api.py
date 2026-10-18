"""API coverage for cognitive continuity routes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gaia.core.event_bus import Event, EventDomain
from gaia.core.runtime import create_runtime
from gaia.server.app import create_app


def test_continuity_is_unavailable_until_configured() -> None:
    client = TestClient(create_app())

    status = client.get("/kernel/continuity")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "unavailable"
    assert body["durable"] is False

    publish = client.post("/kernel/continuity/checkpoints")
    assert publish.status_code == 409
    snapshots = client.get("/kernel/continuity/snapshots")
    assert snapshots.status_code == 409

    runtime_status = client.get("/runtime/status")
    assert runtime_status.json()["continuity"] == "unavailable"


def test_continuity_checkpoint_verify_and_audit(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    client = TestClient(create_app(runtime))

    status = client.get("/kernel/continuity")
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "available"
    assert payload["durable"] is True
    assert payload["local_first"] is True
    assert payload["network"] == "none"
    assert payload["cryptographic_immutability"] is False
    assert payload["encrypted_at_rest"] is False

    submitted = client.post(
        "/kernel/tasks",
        json={"task": "Inspect kernel goal tracking", "capabilities": ["reasoning"]},
    )
    assert submitted.status_code == 200
    goal_id = submitted.json()["result"]["goal"]["id"]

    checkpoints = client.get("/kernel/continuity/checkpoints")
    assert checkpoints.status_code == 200
    listed = checkpoints.json()
    assert listed["count"] >= 1
    assert listed["integrity_ok"] is True
    checkpoint_id = listed["checkpoints"][-1]["checkpoint_id"]

    verified = client.post(f"/kernel/continuity/checkpoints/{checkpoint_id}/verify")
    assert verified.status_code == 200
    assert verified.json()["verified"] is True
    assert verified.json()["cryptographic_immutability"] is False

    tasks = client.get("/kernel/continuity/tasks")
    assert tasks.status_code == 200
    assert any(item["goal_id"] == goal_id for item in tasks.json()["tasks"])

    snapshots = client.get("/kernel/continuity/snapshots")
    assert snapshots.status_code == 200
    environment = snapshots.json()
    assert environment["cryptographic_immutability"] is False
    assert environment["modifies_worktree"] is False
    assert environment["resumes_process"] is False
    assert environment["switches_model"] is False
    assert environment["process"]["model_id"]
    assert environment["process"]["resumes_process"] is False
    assert environment["comparison"]["model_switched"] is False
    assert environment["repository"]["available"] is False
    assert environment["comparison"]["repository_diverged"] is False

    audit = client.get("/kernel/continuity/audit")
    assert audit.status_code == 200
    assert audit.json()["integrity_ok"] is True
    assert audit.json()["approval_events"] == []

    runtime_status = client.get("/runtime/status")
    assert runtime_status.json()["continuity"] == "available"
    assert payload["streaming"] is True
    assert payload["cryptographic_immutability"] is False

    stream = client.get("/kernel/continuity/events/stream", params={"once": "true"})
    assert stream.status_code == 200
    assert "text/event-stream" in stream.headers["content-type"]
    assert "event: snapshot" in stream.text
    data_line = next(line for line in stream.text.splitlines() if line.startswith("data:"))
    snapshot = json.loads(data_line.removeprefix("data:").strip())
    assert snapshot["cryptographic_immutability"] is False
    assert any(item["name"] == "checkpoint_published" for item in snapshot["events"])
    assert all("payload_json" not in item.get("payload", {}) for item in snapshot["events"])


def test_continuity_branch_and_delete_live_goal(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    client = TestClient(create_app(runtime))
    submitted = client.post(
        "/kernel/tasks",
        json={
            "task": "Record a local project note",
            "capabilities": ["reasoning"],
            "metadata": {"api_key": "should-not-persist", "topic": "notes"},
        },
    )
    assert submitted.status_code == 200
    goal = submitted.json()["result"]["goal"]
    assert goal["metadata"]["api_key"] == "[redacted]"
    assert goal["metadata"]["topic"] == "notes"
    goal_id = goal["id"]

    checkpoints = client.get("/kernel/continuity/checkpoints").json()["checkpoints"]
    parent = checkpoints[-1]["checkpoint_id"]
    created = client.post(
        "/kernel/continuity/branches",
        json={
            "parent_checkpoint_id": parent,
            "reason": "try a documented alternative",
            "tool_policy": {"sandbox_required": True, "approval_token": "nope"},
        },
    )
    assert created.status_code == 200
    branch = created.json()["branch"]
    assert branch["tool_policy"]["approval_token"] == "[redacted]"
    assert branch["parent_checkpoint_id"] == parent

    deleted = client.post(
        f"/kernel/continuity/goals/{goal_id}/delete",
        json={"reason": "remove live note"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["published_checkpoints_retained"] is True
    missing = client.get(f"/kernel/goals/{goal_id}")
    assert missing.status_code == 404
    assert client.get("/kernel/continuity/checkpoints").json()["integrity_ok"] is True


def test_continuity_stream_is_unavailable_without_a_journal() -> None:
    client = TestClient(create_app())
    stream = client.get("/kernel/continuity/events/stream", params={"once": "true"})
    assert stream.status_code == 200
    data_line = next(line for line in stream.text.splitlines() if line.startswith("data:"))
    snapshot = json.loads(data_line.removeprefix("data:").strip())
    assert snapshot["status"] == "unavailable"
    assert snapshot["events"] == []


@pytest.mark.asyncio
async def test_continuity_bus_receives_published_checkpoint(tmp_path: Path) -> None:
    runtime = create_runtime(continuity_path=tmp_path / "continuity.sqlite3")
    assert runtime.kernel.continuity is not None
    received: list[Event] = []

    async def capture(event: Event) -> None:
        received.append(event)

    await runtime.event_bus.subscribe(EventDomain.CONTINUITY, capture)
    checkpoint = runtime.kernel.continuity.publish(
        reason="stream-test",
        kernel_id=runtime.kernel.state.kernel_id,
    )
    await asyncio.sleep(0.05)
    names = [event.name for event in received]
    assert "checkpoint_published" in names
    assert any(
        event.payload.get("checkpoint_id") == checkpoint.checkpoint_id for event in received
    )
    recent = runtime.kernel.continuity.recent_events()
    assert recent[-1].name == "checkpoint_published"
    assert "payload_json" not in recent[-1].payload
