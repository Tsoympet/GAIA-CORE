from fastapi.testclient import TestClient

from gaia.server import create_app


def test_kernel_status_and_goal_lifecycle_api() -> None:
    client = TestClient(create_app())

    status = client.get("/kernel/status")
    created = client.post(
        "/kernel/goals",
        json={
            "objective": "Implement the Cognitive Kernel",
            "priority": 90,
            "project_id": "gaia-core",
        },
    )
    goals = client.get("/kernel/goals")

    assert status.status_code == 200
    assert status.json()["state"] == "ready"
    assert created.status_code == 200
    assert created.json()["status"] == "planned"
    assert goals.status_code == 200
    assert goals.json()[0]["objective"] == "Implement the Cognitive Kernel"


def test_task_api_accepts_kernel_budget_and_records_execution() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/tasks",
        json={
            "task": "Analyze the recovered GAIA runtime",
            "capabilities": ["reasoning"],
            "budget": {"max_steps": 2, "max_seconds": 5},
        },
    )
    executions = client.get("/kernel/executions")

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["status"] == "completed"
    assert payload["artifacts"]["kernel"]["verification"]["passed"] is True
    assert executions.status_code == 200
    assert executions.json()[0]["status"] == "completed"


def test_task_api_blocks_preflight_step_budget_violation() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/tasks",
        json={
            "task": "Research and secure the repository",
            "capabilities": ["research", "security"],
            "budget": {"max_steps": 1},
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["status"] == "blocked"
    assert "planned steps" in payload["artifacts"]["kernel"]["reason"]
