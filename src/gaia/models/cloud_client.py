"""Cloud fallback client guarded by explicit configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CloudModelConfig:
    enabled: bool = False
    provider: str = "disabled"
    api_key_secret_name: str | None = None


@dataclass(slots=True)
class CloudFallbackClient:
    config: CloudModelConfig

    async def generate(
        self,
        prompt: str,
        model_id: str,
        **kwargs: object,
    ) -> str:
        del prompt, model_id, kwargs
        if not self.config.enabled:
            raise PermissionError(
                "cloud model fallback is disabled by configuration"
            )
        raise NotImplementedError(
            f"cloud provider {self.config.provider!r} is configured "
            "but no adapter has been installed"
        )
