"""Full R1 regression tests: streaming, backup/restore, permissions, failures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gaia.core.runtime import create_runtime
from gaia.kernel.config import load_kernel_config
from gaia.kernel.goal_manager import GoalStatus
from gaia.security.permission_manager import Permission
from gaia.server import create_app


def test_load_kernel_config_from_yaml() -> None:
    config = load_kernel_config(Path("config"))
    assert config.enabled is True
    assert config.persistence.schema_version == 1
    assert config.budgets.max_steps == 32
    assert config.security.admin_permission == "kernel.admin"


@pytest.mark.asyncio
async def test_backup_restore_and_delete_goal(tmp_path: Path) -> None:
    db_path = tmp_path / "kernel.sqlite3"
    runtime = create_runtime(
        kernel_db_path=db_path,
        grant_local_kernel_admin=True,
    )
    result = await runtime.kernel.run("Backup this goal", "session-dr")
    goal_id = result.goal.id
    backup_path = runtime.kernel.backup(tmp_path / "kernel-backup")

    assert backup_path.exists()
    assert runtime.kernel.delete_goal(goal_id) is True
    assert runtime.kernel.goals.get(goal_id) is None
    assert runtime.kernel.store.get_goal(goal_id) is None

    runtime.kernel.restore(backup_path)
    restored = runtime.kernel.goals.get(goal_id)
    assert restored is not None
    assert restored.status is GoalStatus.COMPLETED
    assert runtime.kernel.contexts.get(goal_id) is not None


@pytest.mark.asyncio
async def test_memory_sql_backup_roundtrip(tmp_path: Path) -> None:
    runtime = create_runtime(grant_local_kernel_admin=True)
    result = await runtime.kernel.run("SQL backup goal", "session-sql")
    backup = runtime.kernel.backup(tmp_path / "memory-backup.sql")
    runtime.kernel.purge()
    assert runtime.kernel.goals.count() == 0

    runtime.kernel.restore(backup)
    assert runtime.kernel.goals.get(result.goal.id) is not None


def test_kernel_admin_routes_require_permissions(tmp_path: Path) -> None:
    runtime = create_runtime()  # KERNEL_READ only
    client = TestClient(create_app(runtime))

    denied = client.post("/kernel/backup", json={"destination": str(tmp_path / "x")})
    assert denied.status_code == 403
    body = denied.json()["detail"]
    assert body["permission"] == "kernel.backup"

    runtime.permission_manager.grant(
        Permission.KERNEL_BACKUP,
        "*",
        "test",
        human_approved=True,
    )
    runtime.permission_manager.grant(
        Permission.KERNEL_ADMIN,
        "*",
        "test",
        human_approved=True,
    )
    runtime.permission_manager.grant(
        Permission.KERNEL_DELETE,
        "*",
        "test",
        human_approved=True,
    )

    created = client.post("/kernel/tasks", json={"task": "admin path"})
    assert created.status_code == 200
    goal_id = created.json()["result"]["goal"]["id"]

    backed = client.post(
        "/kernel/backup",
        json={"destination": str(tmp_path / "api-backup")},
    )
    assert backed.status_code == 200
    assert Path(backed.json()["destination"]).exists()

    deleted = client.delete(f"/kernel/goals/{goal_id}")
    assert deleted.status_code == 200

    missing = client.delete("/kernel/goals/does-not-exist")
    assert missing.status_code == 404


def test_resume_non_interrupted_goal_conflicts() -> None:
    runtime = create_runtime()
    client = TestClient(create_app(runtime))
    created = client.post("/kernel/tasks", json={"task": "completed goal"})
    goal_id = created.json()["result"]["goal"]["id"]

    resumed = client.post(f"/kernel/goals/{goal_id}/resume", json={})
    assert resumed.status_code == 409


def test_kill_switch_blocks_kernel_admission() -> None:
    runtime = create_runtime()
    runtime.permission_manager.activate_kill_switch("r1 regression")
    client = TestClient(create_app(runtime))

    response = client.post("/kernel/tasks", json={"task": "should be blocked"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["goal"]["status"] == "blocked"
    assert result["response"]["status"] == "blocked"


def test_sse_stream_emits_snapshot_and_closes_in_once_mode() -> None:
    runtime = create_runtime()
    client = TestClient(create_app(runtime))

    response = client.get("/kernel/events/stream", params={"once": "true"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: snapshot" in response.text
    payload_line = next(
        line for line in response.text.splitlines() if line.startswith("data:")
    )
    payload = json.loads(payload_line.removeprefix("data:").strip())
    assert "events" in payload


@pytest.mark.asyncio
async def test_purge_removes_live_and_durable_state(tmp_path: Path) -> None:
    runtime = create_runtime(
        kernel_db_path=tmp_path / "purge.sqlite3",
        grant_local_kernel_admin=True,
    )
    await runtime.kernel.run("purge me", "session-purge")
    counts = runtime.kernel.purge()
    assert counts["goals"] >= 1
    assert runtime.kernel.goals.count() == 0
    assert runtime.kernel.contexts.active_count() == 0
    assert runtime.kernel.store.list_goals() == []


def test_kernel_status_includes_config() -> None:
    client = TestClient(create_app())
    payload = client.get("/kernel/status").json()
    assert payload["config"]["enabled"] is True
    assert payload["config"]["budgets"]["max_steps"] == 32
