from fastapi.testclient import TestClient

from gaia.server import create_app


def test_task_endpoint_runs_pipeline() -> None:
    client = TestClient(create_app())

    response = client.post("/tasks", json={"task": "Plan a local-first assistant workflow"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["agents"]
