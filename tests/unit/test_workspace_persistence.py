from pathlib import Path

from gaia.workspaces import SQLiteWorkspaceStore


def test_sqlite_workspace_store_persists_records(tmp_path: Path) -> None:
    db_path = tmp_path / "workspaces.sqlite3"
    first_store = SQLiteWorkspaceStore(db_path)

    created = first_store.create(
        "Phase 4 Workspace",
        description="Durable local workspace",
        metadata={"phase": 4},
    )
    second_store = SQLiteWorkspaceStore(db_path)

    loaded = second_store.get(created.workspace_id)

    assert loaded is not None
    assert loaded.name == "Phase 4 Workspace"
    assert loaded.metadata == {"phase": 4}
    assert second_store.status()["durable"] is True
    assert second_store.status()["workspace_count"] == 1
