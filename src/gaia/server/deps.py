"""Server dependency container for foundation services."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gaia.memory import MemoryManager
from gaia.models import (
    CloudFallbackClient,
    CloudModelConfig,
    ModelDescriptor,
    ModelProvider,
    ModelRegistry,
    ModelRouter,
)
from gaia.security import (
    AutonomyKillSwitch,
    Permission,
    PermissionManager,
    SecurityPolicy,
    create_security_policy,
)
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
        if "gaia-local-placeholder" not in self.registry.models:
            self.registry.register(
                ModelDescriptor(
                    "gaia-local-placeholder",
                    ModelProvider.LOCAL,
                    {"chat"},
                    local_first=True,
                )
            )

    @property
    def kill_switch(self) -> AutonomyKillSwitch:
        """Return the permission manager's canonical kill switch."""
        return self.permissions.kill_switch

    @property
    def model_router(self) -> ModelRouter:
        return ModelRouter.default(
            self.registry,
            CloudFallbackClient(CloudModelConfig(enabled=False)),
        )


services = GaiaServices()


def get_services() -> GaiaServices:
    return services
