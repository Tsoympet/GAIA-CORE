"""Model registry and capability metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ModelProvider(StrEnum):
    OLLAMA = "ollama"
    LOCAL = "local"
    CLOUD = "cloud"


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    model_id: str
    provider: ModelProvider
    capabilities: set[str] = field(default_factory=set)
    context_window: int | None = None
    local_first: bool = True
    enabled: bool = True


@dataclass(slots=True)
class ModelRegistry:
    models: dict[str, ModelDescriptor] = field(default_factory=dict)

    def register(self, descriptor: ModelDescriptor) -> None:
        self.models[descriptor.model_id] = descriptor

    def list(self, capability: str | None = None) -> list[ModelDescriptor]:
        models = [
            model
            for model in self.models.values()
            if model.enabled
        ]
        if capability:
            models = [
                model
                for model in models
                if capability in model.capabilities
            ]
        return sorted(
            models,
            key=lambda model: (
                not model.local_first,
                model.provider.value,
                model.model_id,
            ),
        )

    def get(self, model_id: str) -> ModelDescriptor:
        return self.models[model_id]
