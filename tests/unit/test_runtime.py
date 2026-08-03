from pathlib import Path

from gaia.core import create_runtime


def test_runtime_bootstraps_architecture_components() -> None:
    runtime = create_runtime(config_dir=Path("config"))

    status = runtime.status()

    assert status.configured is True
    assert status.local_first is True
    assert "gaia_core_agent" in status.agents
    assert "gaia_self_evolve_agent" in status.agents
    assert "reasoning" in status.capabilities
    assert "self_evolve" in status.capabilities
    assert status.kernel_status == "idle"
    assert status.kernel_id
    assert runtime.kernel is not None
