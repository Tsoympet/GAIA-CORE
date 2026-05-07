from pathlib import Path

import pytest

from gaia.core.runtime import TaskRequest, create_runtime


@pytest.mark.asyncio
async def test_runtime_accepts_task_and_returns_structured_response() -> None:
    runtime = create_runtime(Path("config"))

    response = await runtime.submit_task(TaskRequest(task="Analyze the GAIA bootstrap runtime"))

    assert response.status == "completed"
    assert response.agents == ["gaia_core_agent"]
    assert response.confidence > 0
    assert response.artifacts["node_count"] == 1
