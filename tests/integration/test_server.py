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
