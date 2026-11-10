import base64

import pytest

from gaia.memory import MemoryManager, MemoryScope
from gaia.models.cloud_client import CloudFallbackClient, CloudModelConfig
from gaia.models.local_client import DETERMINISTIC_MODEL_ID, LocalModelClient
from gaia.models.registry import ModelDescriptor, ModelProvider, ModelRegistry
from gaia.models.router import ModelRouter
from gaia.security.permission_manager import PermissionManager
from gaia.tools import ToolCatalog
from gaia.voice.synthetic_tone import tone_wav
from gaia.voice.tts_engine import TTSEngine, TTSRequest


class _DownOllama:
    async def health(self) -> dict[str, object]:
        return {"provider": "ollama", "available": False, "models": [], "detail": "down"}

    async def generate(self, prompt: str, model_id: str, **kwargs: object) -> str:
        del prompt, model_id, kwargs
        raise AssertionError("ollama should not be called when it is down")


def test_local_client_is_deterministic_and_honest() -> None:
    client = LocalModelClient()
    first = client.compose("Plan a local-first assistant", DETERMINISTIC_MODEL_ID)
    second = client.compose("Plan a local-first assistant", DETERMINISTIC_MODEL_ID)

    assert first == second
    assert "neural_weights_loaded: false" in first
    assert "cloud_fallback: disabled" in first
    assert "Plan a local-first assistant" in first
    assert "Prepared a local plan" in first


def test_local_client_rejects_blank_prompt() -> None:
    with pytest.raises(ValueError, match="prompt must not be empty"):
        LocalModelClient().compose("   ", DETERMINISTIC_MODEL_ID)


@pytest.mark.asyncio
async def test_router_uses_local_client_when_ollama_is_down() -> None:
    registry = ModelRegistry()
    registry.register(
        ModelDescriptor("llama3.1", ModelProvider.OLLAMA, {"chat"}, local_first=True)
    )
    registry.register(
        ModelDescriptor(
            DETERMINISTIC_MODEL_ID,
            ModelProvider.LOCAL,
            {"chat"},
            local_first=True,
        )
    )
    router = ModelRouter.default(
        registry,
        CloudFallbackClient(CloudModelConfig(enabled=False)),
        ollama=_DownOllama(),
    )

    result = await router.complete("Summarize the local policy", capability="chat")
    health = await router.health()

    assert result.provider == "local"
    assert result.deterministic is True
    assert result.local_fallback is True
    assert "Summarize the local policy" in result.text
    assert health["active_provider"] == "local"
    providers = health["providers"]
    assert isinstance(providers, dict)
    cloud = providers["cloud"]
    assert isinstance(cloud, dict)
    assert cloud["enabled"] is False
    assert cloud["available"] is False


@pytest.mark.asyncio
async def test_router_does_not_call_disabled_cloud_model() -> None:
    registry = ModelRegistry()
    registry.register(
        ModelDescriptor("remote-chat", ModelProvider.CLOUD, {"chat"}, local_first=False)
    )
    router = ModelRouter.default(
        registry,
        CloudFallbackClient(CloudModelConfig(enabled=False)),
        ollama=_DownOllama(),
    )

    result = await router.complete("Stay local", model_id="remote-chat")

    assert result.provider == "local"
    assert result.local_fallback is True
    assert "Prepared a local plan" in result.text


def test_tool_status_does_not_execute_and_keeps_shell_gated() -> None:
    permissions = PermissionManager()
    catalog = ToolCatalog()

    status = catalog.status(permissions)
    tools = {item["name"]: item for item in status["tools"]}  # type: ignore[index]

    assert status["execution"] == "status_only"
    assert tools["permission_checked_repo_tools"]["available"] is False
    assert tools["network"]["available"] is False
    assert tools["memory_manager"]["available"] is True
    assert permissions.audit_log.recent() == []


@pytest.mark.asyncio
async def test_model_health_survives_an_absent_ollama_probe() -> None:
    class _RaisingOllama:
        async def health(self) -> dict[str, object]:
            raise ConnectionError("connection refused")

        async def generate(self, prompt: str, model_id: str, **kwargs: object) -> str:
            del prompt, model_id, kwargs
            raise ConnectionError("connection refused")

    registry = ModelRegistry()
    registry.register(
        ModelDescriptor("llama3.1", ModelProvider.OLLAMA, {"chat"}, local_first=True)
    )
    registry.register(
        ModelDescriptor(DETERMINISTIC_MODEL_ID, ModelProvider.LOCAL, {"chat"}, local_first=True)
    )
    router = ModelRouter.default(
        registry,
        CloudFallbackClient(CloudModelConfig(enabled=False)),
        ollama=_RaisingOllama(),
    )

    health = await router.health()

    assert health["active_provider"] == "local"
    assert health["working_model"] == DETERMINISTIC_MODEL_ID
    assert health["ollama_reachable"] is False
    assert health["providers"]["ollama"]["available"] is False
    assert health["providers"]["ollama"]["reachable"] is False
    assert health["providers"]["local"]["available"] is True
    assert health["providers"]["local"]["reachable"] is True
    assert health["providers"]["local"]["neural_weights_loaded"] is False
    assert health["providers"]["cloud"]["enabled"] is False


def test_memory_recall_returns_owner_record() -> None:
    memory = MemoryManager()
    memory.remember("Pump curve at 50 hertz", MemoryScope.PROJECT, "local")
    memory.remember("Unrelated note", MemoryScope.PROJECT, "other")

    matches = memory.recall("pump curve", "local")

    assert len(matches) == 1
    assert matches[0][0].content == "Pump curve at 50 hertz"
    assert matches[0][0].owner_id == "local"


@pytest.mark.asyncio
async def test_synthetic_tone_is_deterministic_wav_and_not_a_clone() -> None:
    first = tone_wav("hello from gaia")
    second = tone_wav("hello from gaia")
    assert first == second
    assert first.startswith(b"RIFF")

    result = await TTSEngine().synthesize(
        TTSRequest(text="hello from gaia", provider="synthetic-tone")
    )
    assert result.status == "synthetic-tone"
    assert result.synthetic is True
    assert result.audio_base64 is not None
    assert base64.b64decode(result.audio_base64).startswith(b"RIFF")

    with pytest.raises(ValueError, match="impersonation"):
        await TTSEngine().synthesize(
            TTSRequest(text="Please sound exactly like a celebrity", provider="synthetic-tone")
        )
