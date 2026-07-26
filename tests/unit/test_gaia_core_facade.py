from pathlib import Path

import pytest

from gaia.core import GaiaCore
from gaia.kernel import ResourceBudget


@pytest.mark.asyncio
async def test_gaia_core_facade_uses_canonical_runtime(tmp_path: Path) -> None:
    core = GaiaCore(workspace=tmp_path / "workspace")

    status = await core.startup()
    response = await core.submit_task(
        "Research local-first model routing",
        capabilities=["research"],
        budget=ResourceBudget(max_steps=2),
    )

    assert status.local_first is True
    assert core.workspace.exists()
    assert response.status == "completed"
    assert response.agents == ["gaia_research_agent"]
    assert response.artifacts["kernel"]["verification"]["passed"] is True


@pytest.mark.asyncio
async def test_gaia_core_creates_sessions_through_runtime(tmp_path: Path) -> None:
    core = GaiaCore(workspace=tmp_path / "workspace")

    session = await core.create_session(
        user_id="operator",
        workspace_id="workspace-1",
        metadata={"purpose": "recovery-test"},
    )

    assert core.runtime.sessions.get(session.id) == session
    assert session.user_id == "operator"
    assert session.workspace_id == "workspace-1"


def test_gaia_core_loads_json_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / "gaia.json"
    config_path.write_text(
        '{"workspace": ".gaia-test", "local_first": true}',
        encoding="utf-8",
    )

    config = GaiaCore.load_config(config_path)

    assert config["workspace"] == ".gaia-test"
    assert config["local_first"] is True
