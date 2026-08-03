"""Integration tests for Cognitive Kernel API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gaia.core import create_runtime
from gaia.server import create_app


def test_kernel_status_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/kernel/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["kernel"]["status"] == "idle"
    assert "kernel_id" in payload["kernel"]


def test_kernel_task_and_goal_inspection() -> None:
    runtime = create_runtime()
    client = TestClient(create_app(runtime))

    submitted = client.post(
        "/kernel/tasks",
        json={"task": "Inspect kernel goal tracking", "capabilities": ["reasoning"]},
    )
    assert submitted.status_code == 200
    result = submitted.json()["result"]
    goal_id = result["goal"]["id"]
    assert result["goal"]["status"] == "completed"
    assert result["verification"]["passed"] is True

    listed = client.get("/kernel/goals")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1

    detail = client.get(f"/kernel/goals/{goal_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["goal"]["id"] == goal_id
    assert body["context"]["items"]
    assert body["budget"] is not None


def test_kernel_cancel_unknown_goal_returns_404() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/kernel/goals/does-not-exist/cancel",
        json={"reason": "test"},
    )

    assert response.status_code == 404


def test_runtime_status_includes_kernel_fields() -> None:
    client = TestClient(create_app())

    payload = client.get("/runtime/status").json()

    assert payload["kernel_status"] == "idle"
    assert payload["kernel_id"]
