"""Phase-4, dream, and metacognition notes survive a new process."""

from pathlib import Path

from fastapi.testclient import TestClient

from gaia.cognition import CognitionNoteStore
from gaia.server.app import create_app
from gaia.server.deps import GaiaServices, get_services
from gaia.workspaces import SQLiteWorkspaceStore


def test_notes_reload_from_sqlite_and_dreams_stay_internal(tmp_path: Path) -> None:
    cognition_db = tmp_path / "cognition.sqlite3"
    workspace_db = tmp_path / "workspaces.sqlite3"
    services = GaiaServices(
        cognition=CognitionNoteStore(cognition_db),
        workspaces=SQLiteWorkspaceStore(workspace_db),
    )
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    client = TestClient(app)

    review = client.post(
        "/metacognition/review",
        json={"answer": "Local plan is ready for operator review.", "signals": {"coverage": 0.4}},
    )
    dream = client.post("/dreaming/cycle", json={"future_goal": "rehearse a local backup"})
    written = client.post(
        "/memory",
        json={
            "owner_id": "local",
            "scope": "project",
            "content": "phase four durable note",
        },
    )

    assert review.status_code == 200
    assert dream.status_code == 200
    assert dream.json()["data"]["external_actions"] is False
    assert written.status_code == 200

    reloaded = GaiaServices(
        cognition=CognitionNoteStore(cognition_db),
        workspaces=SQLiteWorkspaceStore(workspace_db),
    )
    app.dependency_overrides[get_services] = lambda: reloaded

    metacognition = client.get("/metacognition/status").json()["data"]
    assert metacognition["external_actions"] is False
    assert metacognition["durable"] is True
    assert metacognition["last_review"]["critique"]["risks"]
    dreaming = client.get("/dreaming/status").json()["data"]
    assert dreaming["external_actions"] is False
    assert dreaming["blocks_shell"] is True
    assert any("rehearse a local backup" in note for note in dreaming["last_notes"])
    phase4 = client.get(
        "/cognition/notes",
        params={"kind": "phase4", "owner_id": "local"},
    ).json()["data"]
    assert phase4["external_actions"] is False
    assert any(note["body"] == "phase four durable note" for note in phase4["notes"])
    hidden = client.get(
        "/cognition/notes",
        params={"kind": "phase4", "owner_id": "other"},
    ).json()["data"]["notes"]
    assert hidden == []
    direct = CognitionNoteStore(cognition_db)
    assert direct.latest("metacognition") is not None
    assert direct.latest("dream") is not None
