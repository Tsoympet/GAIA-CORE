from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from gaia.server import create_app


def test_health_endpoint_reports_runtime() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["runtime_id"]


def test_status_endpoint_exposes_platform_capabilities() -> None:
    client = TestClient(create_app())

    response = client.get("/runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["local_first"] is True
    assert "coding" in payload["capabilities"]


def test_foundation_route_groups_are_registered() -> None:
    client = TestClient(create_app())

    for path in (
        "/agents/status",
        "/tools/status",
        "/workspaces/status",
        "/self-model/status",
        "/metacognition/status",
        "/dreaming/status",
        "/idle-cognition/status",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["accepted"] is True


def test_phase_two_required_endpoints_are_registered() -> None:
    client = TestClient(create_app())

    for path in (
        "/version",
        "/agents",
        "/capabilities",
        "/memory/status",
        "/runtime/memory/status",
        "/security/status",
    ):
        response = client.get(path)
        assert response.status_code == 200


def test_scoped_and_runtime_memory_status_are_distinct() -> None:
    client = TestClient(create_app())

    scoped = client.get("/memory/status").json()
    runtime = client.get("/runtime/memory/status").json()

    assert "scopes" in scoped
    assert "records" not in scoped
    assert runtime["backend"] == "in-memory"
    assert runtime["append_only"] is True
    assert "records" in runtime


def test_application_has_no_duplicate_method_path_routes() -> None:
    app = create_app()
    route_keys = [
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in sorted(route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    ]

    duplicates = sorted({key for key in route_keys if route_keys.count(key) > 1})
    assert duplicates == []


def test_task_endpoint_rejects_empty_tasks() -> None:
    client = TestClient(create_app())

    response = client.post("/tasks", json={"task": "   "})

    assert response.status_code == 400
    assert "objective must not be empty" in response.json()["detail"]
