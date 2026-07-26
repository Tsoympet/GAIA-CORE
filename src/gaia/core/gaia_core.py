"""High-level compatibility facade for configuring and operating GAIA Core."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from gaia.core.runtime import GaiaRuntime, RuntimeStatus, TaskRequest, create_runtime
from gaia.core.session import Session
from gaia.kernel import ResourceBudget
from gaia.orchestrator.aggregator import AggregatedResponse


class GaiaCore:
    """Small application facade over the canonical recovered ``GaiaRuntime``.

    Earlier repository revisions exposed a second, incompatible runtime through
    this module. The recovery baseline keeps one runtime implementation and uses
    this class only as a convenience wrapper for embedding applications.
    """

    def __init__(
        self,
        *,
        config: Mapping[str, Any] | None = None,
        workspace: str | Path | None = None,
        runtime: GaiaRuntime | None = None,
    ) -> None:
        self.config: dict[str, Any] = dict(config or {})
        configured_workspace = workspace or self.config.get("workspace", ".gaia")
        self.workspace = (
            Path(cast(str | Path, configured_workspace)).expanduser().resolve()
        )
        config_dir = cast(str | Path, self.config.get("config_dir", "config"))
        self.runtime = runtime or create_runtime(config_dir)

    @classmethod
    def from_config_file(
        cls,
        path: str | Path,
        *,
        config_overrides: Mapping[str, Any] | None = None,
        workspace: str | Path | None = None,
        runtime: GaiaRuntime | None = None,
    ) -> GaiaCore:
        """Create a facade from a JSON or TOML configuration file."""
        config = cls.load_config(path)
        config.update(config_overrides or {})
        return cls(config=config, workspace=workspace, runtime=runtime)

    @staticmethod
    def load_config(path: str | Path) -> dict[str, Any]:
        """Load a JSON or TOML configuration object from disk."""
        config_path = Path(path).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(config_path)

        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() == ".json":
            loaded: object = json.loads(text)
        elif config_path.suffix.lower() in {".toml", ".tml"}:
            import tomllib

            loaded = tomllib.loads(text)
        else:
            raise ValueError("unsupported config format; use .json or .toml")

        if not isinstance(loaded, dict):
            raise ValueError("configuration root must be an object")
        return cast(dict[str, Any], loaded)

    async def startup(self) -> RuntimeStatus:
        """Prepare the local workspace and return runtime status."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        return self.runtime.status()

    async def shutdown(self) -> None:
        """Compatibility shutdown hook for embedding applications.

        The current bootstrap runtime owns no background process. Future kernel
        lifecycle services can be connected here without introducing a second
        runtime implementation.
        """

    def status(self) -> RuntimeStatus:
        """Return the canonical runtime status."""
        return self.runtime.status()

    async def create_session(
        self,
        user_id: str = "anonymous",
        *,
        workspace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Create a session through the canonical runtime session manager."""
        return await self.runtime.sessions.create_session(
            user_id=user_id,
            workspace_id=workspace_id,
            metadata=metadata,
        )

    async def submit_task(
        self,
        task: str,
        *,
        capabilities: list[str] | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        goal_id: str | None = None,
        budget: ResourceBudget | None = None,
    ) -> AggregatedResponse:
        """Submit a task through the canonical recovered orchestration runtime."""
        request = TaskRequest(
            task=task,
            session_id=session_id,
            capabilities=capabilities or [],
            metadata=metadata or {},
            goal_id=goal_id,
            budget=budget or ResourceBudget(),
        )
        return await self.runtime.submit_task(request)
