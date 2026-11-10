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


def test_workspace_links_survive_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "workspaces.sqlite3"
    store = SQLiteWorkspaceStore(db_path)
    created = store.create("Pump bench", description="Local project")
    link = store.attach(created.workspace_id, "memory", "mem-bearing-1", label="bearing note")
    store.attach(created.workspace_id, "task", "task-7", label="inspect curve")

    reopened = SQLiteWorkspaceStore(db_path)
    links = reopened.list_links(created.workspace_id)

    assert [item.link_id for item in links][0] == link.link_id
    assert [(item.kind, item.ref_id, item.label) for item in links] == [
        ("memory", "mem-bearing-1", "bearing note"),
        ("task", "task-7", "inspect curve"),
    ]
    assert reopened.status()["link_count"] == 2
