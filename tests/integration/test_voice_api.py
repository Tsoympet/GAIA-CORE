from fastapi.testclient import TestClient

from gaia.server.app import create_app


def test_voice_status_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/voice/status")
    assert response.status_code == 200
    assert response.json()["synthetic_identity"] is True


def test_voice_synthesize_endpoint() -> None:
    client = TestClient(create_app())
    response = client.post("/voice/synthesize", json={"text": "Hello"})
    assert response.status_code == 200
    assert response.json()["status"] == "text-only-fallback"
