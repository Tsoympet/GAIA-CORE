from pathlib import Path

from fastapi.testclient import TestClient

from gaia.server.app import create_app
from gaia.server.deps import GaiaServices, get_services
from gaia.workspaces import SQLiteWorkspaceStore


def test_workspace_api_persists_records_with_sqlite(tmp_path: Path) -> None:
    services = GaiaServices(workspaces=SQLiteWorkspaceStore(tmp_path / "workspaces.sqlite3"))
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    client = TestClient(app)

    created = client.post(
        "/workspaces",
        json={"name": "Phase 4 Workspace", "metadata": {"phase": 4}},
    )

    assert created.status_code == 200
    workspace_id = created.json()["workspace_id"]
    assert client.get(f"/workspaces/{workspace_id}").json()["name"] == "Phase 4 Workspace"

    reloaded_services = GaiaServices(
        workspaces=SQLiteWorkspaceStore(tmp_path / "workspaces.sqlite3")
    )
    app.dependency_overrides[get_services] = lambda: reloaded_services

    persisted = client.get(f"/workspaces/{workspace_id}")
    assert persisted.status_code == 200
    assert persisted.json()["metadata"] == {"phase": 4}
    assert persisted.json()["links"] == []

    attached = client.post(
        f"/workspaces/{workspace_id}/links",
        json={"kind": "memory", "ref_id": "mem-bearing-1", "label": "bearing note"},
    )
    assert attached.status_code == 200
    listed = client.get(f"/workspaces/{workspace_id}/links")
    assert listed.status_code == 200
    assert listed.json()[0]["ref_id"] == "mem-bearing-1"
    assert listed.json()[0]["kind"] == "memory"
    reloaded = client.get(f"/workspaces/{workspace_id}")
    assert reloaded.json()["links"][0]["label"] == "bearing note"
    missing = client.post(
        "/workspaces/missing/links",
        json={"kind": "task", "ref_id": "task-1"},
    )
    assert missing.status_code == 404


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
