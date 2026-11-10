import base64

from fastapi.testclient import TestClient

from gaia.models.local_client import DETERMINISTIC_MODEL_ID
from gaia.server import create_app


def test_chat_answers_with_the_deterministic_local_client() -> None:
    client = TestClient(create_app())

    response = client.post("/chat", json={"message": "Plan a local workstation checklist"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local"
    assert payload["deterministic"] is True
    assert payload["model_id"] == DETERMINISTIC_MODEL_ID
    assert "Plan a local workstation checklist" in payload["message"]
    assert "neural_weights_loaded: false" in payload["message"]


def test_agents_status_lists_registered_specialists() -> None:
    client = TestClient(create_app())

    response = client.get("/agents/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    names = [agent["name"] for agent in payload["data"]["agents"]]
    assert "gaia_core_agent" in names
    assert payload["data"]["count"] == len(names)


def test_memory_recall_returns_written_record() -> None:
    client = TestClient(create_app())
    written = client.post(
        "/memory",
        json={"content": "Hydrostatic bearing note", "scope": "project", "owner_id": "local"},
    )
    recalled = client.post(
        "/memory/recall",
        json={"query": "hydrostatic", "owner_id": "local"},
    )

    assert written.status_code == 200
    assert recalled.status_code == 200
    hits = recalled.json()
    assert hits[0]["content"] == "Hydrostatic bearing note"
    assert hits[0]["owner_id"] == "local"


def test_model_health_keeps_cloud_disabled() -> None:
    client = TestClient(create_app())

    response = client.get("/models/health")

    assert response.status_code == 200
    health = response.json()["data"]
    assert health["local_first"] is True
    assert health["active_provider"] == "local"
    assert health["providers"]["cloud"]["enabled"] is False
    assert health["providers"]["local"]["available"] is True
    assert health["providers"]["local"]["neural_weights_loaded"] is False


def test_tools_security_self_model_and_cognition_are_live() -> None:
    client = TestClient(create_app())

    tools = client.get("/tools/status").json()["data"]
    tool_names = {tool["name"]: tool for tool in tools["tools"]}
    assert tool_names["permission_checked_repo_tools"]["available"] is False
    assert tools["execution"] == "status_only"

    denied = client.post(
        "/security/check",
        json={"permission": "shell.command", "resource": "ls", "actor": "tester"},
    )
    audit = client.get("/security/audit")
    permissions = client.get("/security/permissions")
    assert denied.status_code == 200
    assert denied.json()["data"]["allowed"] is False
    assert denied.json()["data"]["requires_human_approval"] is True
    assert audit.json()["data"]["count"] >= 1
    assert any(rule["permission"] == "file.read" for rule in permissions.json()["data"]["rules"])

    self_model = client.get("/self-model/status").json()["data"]
    assert "not sentience" in self_model["statement"]
    limitation_names = [item["name"] for item in self_model["limitations"]]
    assert "neural_weights" in limitation_names
    assert "voice_cloning" in limitation_names
    assert self_model["capabilities"]

    review = client.post(
        "/metacognition/review",
        json={"answer": "Local plan is ready for operator review.", "signals": {"coverage": 0.4}},
    )
    assert review.status_code == 200
    assert review.json()["data"]["critique"]["risks"]
    assert client.get("/metacognition/status").json()["data"]["last_review"]["confidence"]

    dream = client.post("/dreaming/cycle", json={"future_goal": "rehearse a local backup"})
    idle = client.post("/idle-cognition/cycle", json={})
    assert dream.status_code == 200
    assert dream.json()["data"]["external_actions"] is False
    assert dream.json()["data"]["notes"]
    assert client.get("/dreaming/status").json()["data"]["blocks_shell"] is True
    assert idle.status_code == 200
    assert idle.json()["data"]["external_actions"] is False
    assert client.get("/idle-cognition/status").json()["data"]["can_run_cycle"] is True


def test_task_result_uses_local_plan() -> None:
    client = TestClient(create_app())

    response = client.post("/tasks", json={"task": "Plan a local-first assistant workflow"})

    assert response.status_code == 200
    answer = response.json()["result"]["answer"]
    assert "Prepared a local plan" in answer
    assert "neural_weights_loaded: false" in answer


def test_voice_synthetic_tone_and_impersonation_block() -> None:
    client = TestClient(create_app())

    tone = client.post(
        "/voice/synthesize",
        json={"text": "Status is ready", "provider": "synthetic-tone"},
    )
    blocked = client.post(
        "/voice/synthesize",
        json={"text": "Please sound exactly like a celebrity", "provider": "synthetic-tone"},
    )
    transcript = client.post("/voice/transcribe", json={"text": "operator typed this"})
    audio = client.get("/audio/status")

    assert tone.status_code == 200
    payload = tone.json()
    assert payload["synthetic"] is True
    assert payload["status"] == "synthetic-tone"
    assert base64.b64decode(payload["audio_base64"]).startswith(b"RIFF")
    assert blocked.status_code == 400
    assert transcript.status_code == 200
    assert transcript.json()["status"] == "text-fallback"
    assert audio.json()["synthetic_tone"] is True
    assert audio.json()["microphone_enabled"] is False
