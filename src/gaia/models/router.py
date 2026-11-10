"""Capability-aware local-first model router."""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from gaia.models.cloud_client import CloudFallbackClient
from gaia.models.local_client import DETERMINISTIC_MODEL_ID, LocalModelClient, ModelClient
from gaia.models.ollama_client import OllamaClient
from gaia.models.registry import ModelDescriptor, ModelProvider, ModelRegistry


@dataclass(frozen=True, slots=True)
class ModelGeneration:
    """One completed local-first generation."""

    text: str
    model_id: str
    provider: str
    local_fallback: bool
    deterministic: bool


@dataclass(slots=True)
class ModelRouter:
    registry: ModelRegistry
    ollama: ModelClient
    local: ModelClient
    cloud: CloudFallbackClient
    _health_at: float = 0.0
    _health_report: dict[str, object] | None = None
    _health_ttl_seconds: float = 5.0
    _cache_clock: Callable[[], float] = field(default=time.monotonic, repr=False)

    @classmethod
    def default(
        cls,
        registry: ModelRegistry,
        cloud: CloudFallbackClient,
        ollama: ModelClient | None = None,
        local: ModelClient | None = None,
    ) -> ModelRouter:
        return cls(
            registry=registry,
            ollama=ollama or OllamaClient(),
            local=local or LocalModelClient(),
            cloud=cloud,
        )

    async def generate(
        self,
        prompt: str,
        capability: str = "chat",
        model_id: str | None = None,
    ) -> str:
        return (await self.complete(prompt, capability, model_id)).text

    async def complete(
        self,
        prompt: str,
        capability: str = "chat",
        model_id: str | None = None,
    ) -> ModelGeneration:
        """Generate text, preferring a ready local model and never a disabled cloud."""
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        ollama_health = await self._ollama_health()
        if model_id:
            try:
                candidates = [self.registry.get(model_id)]
            except KeyError as exc:
                raise LookupError(f"unknown model: {model_id}") from exc
        else:
            candidates = self.registry.list(capability)
        skipped: list[str] = []
        for descriptor in self._ordered(candidates, ollama_health):
            skip = self._skip_reason(descriptor, ollama_health)
            if skip is not None:
                skipped.append(skip)
                continue
            try:
                client = self._client_for(descriptor.provider)
                text = await client.generate(prompt, descriptor.model_id)
            except Exception as exc:  # noqa: BLE001
                skipped.append(f"{descriptor.model_id}: {exc}")
                continue
            deterministic = descriptor.provider == ModelProvider.LOCAL
            ollama_unready = any(
                candidate.provider == ModelProvider.OLLAMA
                and not self._ollama_ready(candidate, ollama_health)
                for candidate in candidates
            )
            return ModelGeneration(
                text=text,
                model_id=descriptor.model_id,
                provider=descriptor.provider.value,
                local_fallback=deterministic and (bool(skipped) or ollama_unready),
                deterministic=deterministic,
            )
        local_id = DETERMINISTIC_MODEL_ID
        text = await self.local.generate(prompt, local_id)
        return ModelGeneration(
            text=text,
            model_id=local_id,
            provider=ModelProvider.LOCAL.value,
            local_fallback=True,
            deterministic=True,
        )

    async def health(self) -> dict[str, object]:
        """Report local client status and whether Ollama can be reached.

        A missing daemon, a refused connection, or a probe error leaves this
        report successful. The deterministic local client remains the working
        path in that case. Cloud calls stay disabled unless configured.
        """
        ollama_health = await self._ollama_health()
        local_health = self._local_health()
        cloud_health = self._cloud_health()
        ready_models = [
            model.model_id
            for model in self.registry.list()
            if model.provider == ModelProvider.OLLAMA
            and self._ollama_ready(model, ollama_health)
        ]
        ollama_reachable = bool(ollama_health.get("reachable"))
        listed = ollama_health.get("models")
        ollama_models = (
            [name for name in listed if isinstance(name, str)] if isinstance(listed, list) else []
        )
        return {
            "local_first": True,
            "active_provider": "ollama" if ready_models else "local",
            "working_model": ready_models[0] if ready_models else DETERMINISTIC_MODEL_ID,
            "ollama_reachable": ollama_reachable,
            "ollama_models": ollama_models,
            "local_client": local_health,
            "providers": {
                "local": local_health,
                "ollama": ollama_health,
                "cloud": cloud_health,
            },
        }

    def _ordered(
        self,
        candidates: list[ModelDescriptor],
        ollama_health: dict[str, object],
    ) -> list[ModelDescriptor]:
        def rank(descriptor: ModelDescriptor) -> tuple[int, str]:
            if descriptor.provider == ModelProvider.OLLAMA and self._ollama_ready(
                descriptor, ollama_health
            ):
                group = 0
            elif descriptor.provider == ModelProvider.LOCAL:
                group = 1
            elif descriptor.provider == ModelProvider.CLOUD and self.cloud.config.enabled:
                group = 2
            else:
                group = 3
            return (group, descriptor.model_id)

        return sorted(candidates, key=rank)

    def _skip_reason(
        self,
        descriptor: ModelDescriptor,
        ollama_health: dict[str, object],
    ) -> str | None:
        if not descriptor.enabled:
            return f"{descriptor.model_id} is disabled"
        if descriptor.provider == ModelProvider.CLOUD and not self.cloud.config.enabled:
            return "cloud model fallback is disabled by configuration"
        if descriptor.provider == ModelProvider.OLLAMA and not self._ollama_ready(
            descriptor, ollama_health
        ):
            return f"ollama model {descriptor.model_id} is not available"
        return None

    def _ollama_ready(
        self,
        descriptor: ModelDescriptor,
        ollama_health: dict[str, object],
    ) -> bool:
        if ollama_health.get("available") is not True:
            return False
        models = ollama_health.get("models")
        if models is None:
            return True
        if not isinstance(models, list):
            return False
        return any(
            isinstance(name, str) and _model_listed(descriptor.model_id, name) for name in models
        )

    async def _ollama_health(self) -> dict[str, object]:
        now = float(self._cache_clock())
        cached = self._health_report
        if cached is not None and now - self._health_at < self._health_ttl_seconds:
            return cached
        probe = getattr(self.ollama, "health", None)
        if probe is None:
            report: dict[str, object] = {
                "provider": "ollama",
                "available": True,
                "models": None,
                "detail": "unprobed",
            }
        else:
            try:
                result = probe()
                if inspect.isawaitable(result):
                    probed = await result
                else:
                    probed = result
            except Exception as exc:  # noqa: BLE001
                probed = {
                    "provider": "ollama",
                    "available": False,
                    "models": [],
                    "detail": type(exc).__name__,
                }
            report = probed if isinstance(probed, dict) else {
                "provider": "ollama",
                "available": False,
                "models": [],
                "detail": "invalid health report",
            }
        report = _with_reachability(report, "ollama")
        self._health_at = now
        self._health_report = report
        return report

    def _local_health(self) -> dict[str, object]:
        fallback = {
            "provider": "local",
            "model_id": DETERMINISTIC_MODEL_ID,
            "available": True,
            "deterministic": True,
            "neural_weights_loaded": False,
            "detail": (
                "Deterministic local client is the working path when Ollama "
                "has no ready model."
            ),
        }
        probe = getattr(self.local, "health", None)
        if probe is None:
            return _with_reachability(fallback, "local")
        try:
            result = probe()
        except Exception as exc:  # noqa: BLE001
            fallback["available"] = False
            fallback["detail"] = type(exc).__name__
            return _with_reachability(fallback, "local")
        if isinstance(result, dict):
            return _with_reachability(result, "local")
        return _with_reachability(fallback, "local")

    def _cloud_health(self) -> dict[str, object]:
        try:
            report = self.cloud.health()
        except Exception as exc:  # noqa: BLE001
            report = {
                "provider": "cloud",
                "enabled": False,
                "available": False,
                "detail": type(exc).__name__,
            }
        if not isinstance(report, dict):
            report = {"provider": "cloud", "enabled": False, "available": False}
        return _with_reachability(report, "cloud")

    def _client_for(self, provider: ModelProvider) -> ModelClient:
        if provider == ModelProvider.OLLAMA:
            return self.ollama
        if provider == ModelProvider.LOCAL:
            return self.local
        return self.cloud


def _with_reachability(report: dict[str, object], provider: str) -> dict[str, object]:
    """Attach a boolean reachability flag without raising."""
    marked = dict(report)
    marked.setdefault("provider", provider)
    available = marked.get("available") is True
    marked["reachable"] = available
    if "models" not in marked:
        marked["models"] = []
    return marked


def _model_listed(model_id: str, tag: str) -> bool:
    base = tag.split(":", 1)[0]
    return tag == model_id or base == model_id or tag.startswith(f"{model_id}:")
