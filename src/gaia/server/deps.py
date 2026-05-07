"""Server dependency container for foundation services."""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.memory import MemoryManager
from gaia.models import CloudFallbackClient, CloudModelConfig, ModelDescriptor, ModelProvider, ModelRegistry, ModelRouter
from gaia.security import AutonomyKillSwitch, Permission, PermissionManager


@dataclass(slots=True)
class GaiaServices:
    permissions: PermissionManager = field(default_factory=PermissionManager)
    memory: MemoryManager = field(default_factory=MemoryManager)
    registry: ModelRegistry = field(default_factory=ModelRegistry)
    kill_switch: AutonomyKillSwitch = field(default_factory=AutonomyKillSwitch)

    def __post_init__(self) -> None:
        self.permissions.grant(Permission.FILE_READ, "*", "bootstrap local read")
        self.registry.register(
            ModelDescriptor("llama3.1", ModelProvider.OLLAMA, {"chat", "reasoning"}, local_first=True)
        )
        self.registry.register(
            ModelDescriptor("gaia-local-placeholder", ModelProvider.LOCAL, {"chat"}, local_first=True)
        )

    @property
    def model_router(self) -> ModelRouter:
        return ModelRouter.default(self.registry, CloudFallbackClient(CloudModelConfig(enabled=False)))


services = GaiaServices()


def get_services() -> GaiaServices:
    return services
