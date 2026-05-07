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
