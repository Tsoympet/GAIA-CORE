"""High-level facade for configuring and operating GAIA Core."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .context import ExecutionContext, MemoryHook, SecurityContext
from .event_bus import EventBus
from .lifecycle import LifecycleHook, LifecycleManager
from .runtime import GaiaRuntime, TaskCallable, TaskRecord
from .session import Session, SessionManager

AgentHandler = TaskCallable
OrchestratorHandler = Callable[[Any, ExecutionContext, dict[str, AgentHandler]], Awaitable[Any] | Any]


class GaiaCore:
    """Convenience facade for applications embedding the GAIA runtime."""

    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        workspace: str | Path | None = None,
        event_bus: EventBus | None = None,
        runtime: GaiaRuntime | None = None,
        sessions: SessionManager | None = None,
    ) -> None:
        self.config = config or {}
        self.workspace = Path(workspace or self.config.get("workspace", ".gaia")).expanduser().resolve()
        self.event_bus = event_bus or EventBus()
        self.lifecycle = LifecycleManager()
        self.runtime = runtime or GaiaRuntime(event_bus=self.event_bus, lifecycle=self.lifecycle)
        self.sessions = sessions or SessionManager()
        self.agents: dict[str, AgentHandler] = {}
        self.orchestrators: dict[str, OrchestratorHandler] = {}
        self.memory_hooks: list[MemoryHook] = []

    @classmethod
    def from_config_file(cls, path: str | Path, **overrides: Any) -> "GaiaCore":
        """Create a facade from a JSON or TOML configuration file."""

        config_path = Path(path).expanduser()
        data = cls.load_config(config_path)
        data.update(overrides.pop("config", {}))
        return cls(config=data, **overrides)

    @staticmethod
    def load_config(path: str | Path) -> dict[str, Any]:
        """Load JSON or TOML configuration from disk."""

        config_path = Path(path).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(config_path)
        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() == ".json":
            loaded = json.loads(text)
        elif config_path.suffix.lower() in {".toml", ".tml"}:
            import tomllib

            loaded = tomllib.loads(text)
        else:
            raise ValueError("unsupported config format; use .json or .toml")
        if not isinstance(loaded, dict):
            raise ValueError("configuration root must be an object")
        return loaded

    async def startup(self) -> None:
        """Prepare workspace storage and start the async runtime."""

        self.workspace.mkdir(parents=True, exist_ok=True)
        await self.runtime.start()

    async def shutdown(self) -> None:
        """Shut down runtime services."""

        await self.runtime.shutdown()

    def register_agent(
        self,
        name: str,
        handler: AgentHandler | None = None,
    ) -> AgentHandler | Callable[[AgentHandler], AgentHandler]:
        """Register an agent callable by name, directly or as a decorator."""

        def decorator(agent_handler: AgentHandler) -> AgentHandler:
            self.agents[name] = agent_handler
            return agent_handler

        if handler is None:
            return decorator
        return decorator(handler)

    def register_orchestrator(
        self,
        name: str,
        handler: OrchestratorHandler | None = None,
    ) -> OrchestratorHandler | Callable[[OrchestratorHandler], OrchestratorHandler]:
        """Register an orchestrator callable by name, directly or as a decorator."""

        def decorator(orchestrator_handler: OrchestratorHandler) -> OrchestratorHandler:
            self.orchestrators[name] = orchestrator_handler
            return orchestrator_handler

        if handler is None:
            return decorator
        return decorator(handler)

    def register_memory_hook(self, hook: MemoryHook) -> MemoryHook:
        """Register a hook invoked by execution contexts for memory side effects."""

        self.memory_hooks.append(hook)
        return hook

    def on_startup(self, hook: LifecycleHook) -> LifecycleHook:
        return self.lifecycle.on_startup(hook)

    def on_shutdown(self, hook: LifecycleHook) -> LifecycleHook:
        return self.lifecycle.on_shutdown(hook)

    async def create_session(
        self,
        user_id: str = "anonymous",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        return await self.sessions.create_session(user_id=user_id, metadata=metadata)

    async def build_context(
        self,
        *,
        session: Session | None = None,
        session_id: str | None = None,
        security: SecurityContext | None = None,
    ) -> ExecutionContext:
        """Build an execution context for a request."""

        if session is None and session_id is not None:
            session = await self.sessions.require_session(session_id)
        if session is None:
            session = await self.create_session()
        return ExecutionContext(
            session=session,
            workspace=self.workspace,
            config=self.config,
            security=security or SecurityContext(principal=session.user_id),
            memory_hooks=list(self.memory_hooks),
        )

    async def submit_task(
        self,
        name: str,
        payload: Any,
        *,
        agent: str | None = None,
        orchestrator: str | None = None,
        context: ExecutionContext | None = None,
        session_id: str | None = None,
    ) -> TaskRecord:
        """Submit work to an agent or orchestrator."""

        if (agent is None) == (orchestrator is None):
            raise ValueError("provide exactly one of agent or orchestrator")
        context = context or await self.build_context(session_id=session_id)
        if agent is not None:
            handler = self.agents[agent]
            task_name = f"agent:{agent}:{name}"
        else:
            orchestrator_handler = self.orchestrators[orchestrator or ""]

            async def handler(data: Any, ctx: ExecutionContext) -> Any:
                result = orchestrator_handler(data, ctx, self.agents)
                if hasattr(result, "__await__"):
                    return await result
                return result

            task_name = f"orchestrator:{orchestrator}:{name}"
        return await self.runtime.submit(task_name, handler, payload, context)
