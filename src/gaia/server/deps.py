"""Server dependency container for foundation services."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gaia.cognition import CognitionNoteStore
from gaia.dreaming.dream_engine import DreamEngine, DreamReport
from gaia.dreaming.idle_scheduler import IdleScheduler
from gaia.memory import MemoryManager
from gaia.memory.memory_manager import MemoryManager as RuntimeMemoryManager
from gaia.metacognition.reflection_loop import ReflectionLoop, ReflectionReport
from gaia.models import (
    CloudFallbackClient,
    CloudModelConfig,
    ModelDescriptor,
    ModelProvider,
    ModelRegistry,
    ModelRouter,
)
from gaia.models.local_client import DETERMINISTIC_MODEL_ID
from gaia.security import (
    AutonomyKillSwitch,
    Permission,
    PermissionManager,
    SecurityPolicy,
    create_security_policy,
)
from gaia.tools import ToolCatalog
from gaia.workspaces import SQLiteWorkspaceStore


@dataclass(slots=True)
class GaiaServices:
    """Services used by modular API routes."""

    permissions: PermissionManager = field(default_factory=PermissionManager)
    security_policy: SecurityPolicy = field(default_factory=create_security_policy)
    memory: MemoryManager = field(default_factory=MemoryManager)
    registry: ModelRegistry = field(default_factory=ModelRegistry)
    workspaces: SQLiteWorkspaceStore = field(
        default_factory=lambda: SQLiteWorkspaceStore(Path(".gaia/workspaces.sqlite3"))
    )
    reflection: ReflectionLoop = field(default_factory=ReflectionLoop)
    dream_engine: DreamEngine = field(default_factory=DreamEngine)
    idle_scheduler: IdleScheduler = field(default_factory=IdleScheduler)
    dream_memory: RuntimeMemoryManager = field(default_factory=RuntimeMemoryManager)
    idle_memory: RuntimeMemoryManager = field(default_factory=RuntimeMemoryManager)
    tools: ToolCatalog = field(default_factory=ToolCatalog)
    cognition: CognitionNoteStore = field(
        default_factory=lambda: CognitionNoteStore(Path(".gaia/cognition.sqlite3"))
    )
    last_reflection: ReflectionReport | None = None
    last_dream: DreamReport | None = None
    last_idle: DreamReport | None = None
    _model_router: ModelRouter | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not any(
            rule.permission == Permission.FILE_READ and rule.resource_pattern == "*"
            for rule in self.permissions.rules
        ):
            self.permissions.grant(Permission.FILE_READ, "*", "bootstrap local read")

        if "llama3.1" not in self.registry.models:
            self.registry.register(
                ModelDescriptor(
                    "llama3.1",
                    ModelProvider.OLLAMA,
                    {"chat", "reasoning"},
                    local_first=True,
                )
            )
        if DETERMINISTIC_MODEL_ID not in self.registry.models:
            self.registry.register(
                ModelDescriptor(
                    DETERMINISTIC_MODEL_ID,
                    ModelProvider.LOCAL,
                    {"chat", "reasoning", "planning"},
                    local_first=True,
                )
            )

    @property
    def kill_switch(self) -> AutonomyKillSwitch:
        """Return the permission manager's canonical kill switch."""
        return self.permissions.kill_switch

    @property
    def model_router(self) -> ModelRouter:
        if self._model_router is None:
            self._model_router = ModelRouter.default(
                self.registry,
                CloudFallbackClient(CloudModelConfig(enabled=False)),
            )
        return self._model_router


services = GaiaServices()


def get_services() -> GaiaServices:
    return services
