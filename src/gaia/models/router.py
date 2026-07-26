"""Capability-aware local-first model router."""

from __future__ import annotations

from dataclasses import dataclass

from gaia.models.cloud_client import CloudFallbackClient
from gaia.models.local_client import LocalModelClient, ModelClient
from gaia.models.ollama_client import OllamaClient
from gaia.models.registry import ModelProvider, ModelRegistry


@dataclass(slots=True)
class ModelRouter:
    registry: ModelRegistry
    ollama: ModelClient
    local: ModelClient
    cloud: CloudFallbackClient

    @classmethod
    def default(
        cls,
        registry: ModelRegistry,
        cloud: CloudFallbackClient,
    ) -> ModelRouter:
        return cls(
            registry=registry,
            ollama=OllamaClient(),
            local=LocalModelClient(),
            cloud=cloud,
        )

    async def generate(
        self,
        prompt: str,
        capability: str = "chat",
        model_id: str | None = None,
    ) -> str:
        candidates = (
            [self.registry.get(model_id)]
            if model_id
            else self.registry.list(capability)
        )
        if not candidates:
            raise LookupError(
                f"no enabled model registered for capability: {capability}"
            )
        last_error: Exception | None = None
        for descriptor in candidates:
            try:
                client = self._client_for(descriptor.provider)
                return await client.generate(prompt, descriptor.model_id)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise RuntimeError(
            f"all model candidates failed: {last_error}"
        ) from last_error

    def _client_for(self, provider: ModelProvider) -> ModelClient:
        if provider == ModelProvider.OLLAMA:
            return self.ollama
        if provider == ModelProvider.LOCAL:
            return self.local
        return self.cloud
