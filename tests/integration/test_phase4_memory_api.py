from pathlib import Path

from fastapi.testclient import TestClient

from gaia.cognition import CognitionNoteStore
from gaia.memory import MemoryManager
from gaia.memory.indexer import SQLITE_VECTOR_INDEX
from gaia.memory.sqlite_index import SQLiteVectorIndex
from gaia.server.app import create_app
from gaia.server.deps import GaiaServices, get_services
from gaia.workspaces import SQLiteWorkspaceStore


def _services(tmp_path: Path) -> GaiaServices:
    return GaiaServices(
        memory=MemoryManager(vector_store=SQLiteVectorIndex(tmp_path / "phase4.sqlite3")),
        workspaces=SQLiteWorkspaceStore(tmp_path / "workspaces.sqlite3"),
        cognition=CognitionNoteStore(tmp_path / "cognition.sqlite3"),
    )


def test_workspace_api_persists_records_with_sqlite(tmp_path: Path) -> None:
    services = _services(tmp_path)
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    client = TestClient(app)

    written = client.post(
        "/memory",
        json={
            "owner_id": "local",
            "scope": "project",
            "content": "Hydrostatic bearing note for the bench",
        },
    )
    assert written.status_code == 200
    record_id = written.json()["record_id"]

    created = client.post(
        "/workspaces",
        json={"name": "Phase 4 Workspace", "metadata": {"phase": 4}},
    )

    assert created.status_code == 200
    workspace_id = created.json()["workspace_id"]
    assert client.get(f"/workspaces/{workspace_id}").json()["name"] == "Phase 4 Workspace"

    reloaded_services = _services(tmp_path)
    app.dependency_overrides[get_services] = lambda: reloaded_services

    persisted = client.get(f"/workspaces/{workspace_id}")
    assert persisted.status_code == 200
    assert persisted.json()["metadata"] == {"phase": 4}
    assert persisted.json()["links"] == []

    attached = client.post(
        f"/workspaces/{workspace_id}/links",
        json={"kind": "memory", "ref_id": record_id, "label": "bearing note"},
    )
    assert attached.status_code == 200
    assert attached.json()["target_exists"] is True
    unknown = client.post(
        f"/workspaces/{workspace_id}/links",
        json={"kind": "memory", "ref_id": "mem-bearing-1", "label": "missing note"},
    )
    assert unknown.status_code == 400
    assert unknown.json()["detail"] == "unknown memory reference: mem-bearing-1"
    goal = app.state.runtime.kernel.goals.create("Inspect the pump curve", "local")
    task_link = client.post(
        f"/workspaces/{workspace_id}/links",
        json={"kind": "task", "ref_id": goal.id, "label": "inspect curve"},
    )
    assert task_link.status_code == 200
    assert task_link.json()["target_exists"] is True
    unknown_task = client.post(
        f"/workspaces/{workspace_id}/links",
        json={"kind": "task", "ref_id": "task-missing"},
    )
    assert unknown_task.status_code == 400
    assert unknown_task.json()["detail"] == "unknown task reference: task-missing"
    listed = client.get(f"/workspaces/{workspace_id}/links")
    assert listed.status_code == 200
    by_kind = {item["kind"]: item for item in listed.json()}
    assert by_kind["memory"]["ref_id"] == record_id
    assert by_kind["memory"]["target_exists"] is True
    assert by_kind["task"]["target_exists"] is True
    reloaded = client.get(f"/workspaces/{workspace_id}")
    assert reloaded.json()["links"][0]["label"] == "bearing note"
    deletion = client.post(
        "/memory/deletion-requests",
        json={"owner_id": "local", "scope": "project", "reason": "remove the bench note"},
    )
    approved = client.post(
        f"/memory/deletion-requests/{deletion.json()['request_id']}/review",
        json={"approve": True},
    )
    assert approved.status_code == 200
    after_delete = client.get(f"/workspaces/{workspace_id}/links")
    after_kind = {item["kind"]: item for item in after_delete.json()}
    assert after_kind["memory"]["target_exists"] is False
    assert after_kind["task"]["target_exists"] is True
    missing = client.post(
        "/workspaces/missing/links",
        json={"kind": "task", "ref_id": goal.id},
    )
    assert missing.status_code == 404


def test_ranked_recall_survives_a_new_process(tmp_path: Path) -> None:
    phase4_db = tmp_path / "phase4.sqlite3"
    first = create_app(phase4_db=phase4_db)
    client = TestClient(first)
    written = client.post(
        "/memory",
        json={
            "owner_id": "local",
            "scope": "project",
            "content": "Pump curve at 50 hertz stays on disk",
        },
    )
    assert written.status_code == 200
    first.state.services.memory.vector_store.close()

    restarted = TestClient(create_app(phase4_db=phase4_db))
    recalled = restarted.post(
        "/memory/recall",
        json={"query": "pump curve", "owner_id": "local"},
    )
    assert recalled.status_code == 200
    hits = recalled.json()
    assert hits[0]["content"] == "Pump curve at 50 hertz stays on disk"
    assert hits[0]["source"] == "vector"
    assert hits[0]["score_calibrated"] is False
    assert hits[0]["score"] > 0.2
    status = restarted.get("/memory/status").json()
    assert status["vector_index"] == SQLITE_VECTOR_INDEX
    assert status["scores_calibrated"] is False
    assert "uncalibrated" in status["score_note"]
    assert status["indexed_documents"] == 1


def test_memory_review_api_exports_and_deletes_after_review(tmp_path: Path) -> None:
    services = GaiaServices(workspaces=SQLiteWorkspaceStore(tmp_path / "workspaces.sqlite3"))
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    client = TestClient(app)

    grant = client.post("/memory/consent/grant", json={"owner_id": "workspace-1"})
    written = client.post(
        "/memory",
        json={
            "owner_id": "workspace-1",
            "scope": "project",
            "content": "Durable workspace memory review note",
        },
    )
    reviewed = client.get("/memory/review", params={"owner_id": "workspace-1"})
    exported = client.get("/memory/export/workspace-1")
    deletion = client.post(
        "/memory/deletion-requests",
        json={
            "owner_id": "workspace-1",
            "scope": "project",
            "reason": "cleanup after review",
        },
    )
    request_id = deletion.json()["request_id"]
    approved = client.post(
        f"/memory/deletion-requests/{request_id}/review",
        json={"approve": True},
    )

    assert grant.status_code == 200
    assert written.status_code == 200
    assert reviewed.status_code == 200
    assert reviewed.json()[0]["content"] == "Durable workspace memory review note"
    assert exported.json()["scopes"]["project"][0]["content"] == written.json()["content"]
    assert deletion.status_code == 200
    assert approved.json()["status"] == "approved"
    assert client.get("/memory/review", params={"owner_id": "workspace-1"}).json() == []
