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
    assert hits[0]["source"] == "vector"
    assert hits[0]["score_calibrated"] is False
    status = client.get("/memory/status").json()
    assert status["scores_calibrated"] is False
    assert status["vector_index"] == "in-process-hashed-ngram"
    assert "uncalibrated" in status["score_note"]

    fact = client.post(
        "/memory/facts",
        json={
            "subject": "bearing",
            "predicate": "prefers",
            "object_value": "local-notes",
            "owner_id": "local",
            "confidence": 0.4,
        },
    )
    assert fact.status_code == 200
    assert fact.json()["score_calibrated"] is False
    listed = client.get("/memory/facts", params={"owner_id": "local"})
    assert listed.status_code == 200
    assert listed.json()[0]["object_value"] == "local-notes"
    recalled = client.post(
        "/memory/recall",
        json={"query": "bearing prefers local-notes", "owner_id": "local"},
    )
    sources = {hit["source"] for hit in recalled.json()}
    assert "symbolic" in sources
    assert all(hit["score_calibrated"] is False for hit in recalled.json())


def test_unowned_symbolic_fact_is_hidden_from_owner_recall() -> None:
    app = create_app()
    client = TestClient(app)
    app.state.services.memory.add_fact("secret", "visible-to", "everyone")
    owned = client.post(
        "/memory/facts",
        json={
            "subject": "bearing",
            "predicate": "prefers",
            "object_value": "local-notes",
            "owner_id": "local",
        },
    )

    assert owned.status_code == 200
    listed = client.get("/memory/facts", params={"owner_id": "local"})
    subjects = [fact["subject"] for fact in listed.json()]
    assert subjects == ["bearing"]
    assert all(fact["owner_id"] == "local" for fact in listed.json())
    other = client.get("/memory/facts", params={"owner_id": "other"})
    assert other.json() == []
    leaked = client.post(
        "/memory/recall",
        json={"query": "secret visible-to everyone", "owner_id": "local"},
    )
    assert leaked.status_code == 200
    assert all("secret" not in hit["content"] for hit in leaked.json())
    assert all(hit["owner_id"] == "local" for hit in leaked.json())


def test_model_health_keeps_cloud_disabled() -> None:
    client = TestClient(create_app())

    response = client.get("/models/health")

    assert response.status_code == 200
    health = response.json()["data"]
    assert health["local_first"] is True
    assert health["active_provider"] == "local"
    assert health["providers"]["cloud"]["enabled"] is False
    assert health["providers"]["local"]["available"] is True
    assert health["providers"]["local"]["reachable"] is True
    assert health["providers"]["local"]["neural_weights_loaded"] is False
    assert health["local_client"]["model_id"] == DETERMINISTIC_MODEL_ID
    assert isinstance(health["ollama_reachable"], bool)
    assert health["providers"]["ollama"]["reachable"] == health["ollama_reachable"]
    if health["ollama_reachable"] is False:
        assert health["active_provider"] == "local"
        assert health["working_model"] == DETERMINISTIC_MODEL_ID


def test_tools_security_self_model_and_cognition_are_live() -> None:
    client = TestClient(create_app())

    tools = client.get("/tools/status").json()["data"]
    tool_names = {tool["name"]: tool for tool in tools["tools"]}
    assert tool_names["permission_checked_repo_tools"]["available"] is False
    assert tools["execution"] == "status_only"
    assert tool_names["local_clock"]["executable"] is True
    assert tool_names["permission_checked_repo_tools"]["executable"] is False
    assert tool_names["network"]["executable"] is False
    assert tool_names["file_write"]["executable"] is False

    clock = client.post("/tools/run", json={"name": "local_clock", "text": "bench"})
    assert clock.status_code == 200
    assert clock.json()["data"]["executed"] is True
    assert clock.json()["data"]["shell"] is False
    assert clock.json()["data"]["network"] is False
    assert clock.json()["data"]["files_touched"] is False
    assert clock.json()["data"]["result"]["echo"] == "bench"
    for blocked_name in ("permission_checked_repo_tools", "network", "file_write", "file_read"):
        blocked = client.post("/tools/run", json={"name": blocked_name, "text": "ls"})
        assert blocked.status_code == 403
        assert "not executed" in blocked.json()["detail"]
    assert client.post("/tools/run", json={"name": "shell"}).status_code == 404

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

    paused = client.post("/security/kill-switch", params={"reason": "operator pause"})
    assert paused.status_code == 200
    assert client.get("/security/status").json()["autonomy_kill_switch"] is True
    assert client.delete("/security/kill-switch").status_code == 200
    assert client.get("/security/status").json()["autonomy_kill_switch"] is False

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
