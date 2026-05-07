"""Local-first AI model catalog."""

from pydantic import BaseModel, Field


class ModelProvider(BaseModel):
    """Model provider configuration metadata."""

    name: str
    provider_type: str
    enabled: bool = True
    local: bool = True


class ModelCatalog(BaseModel):
    """Catalog of available model backends."""

    local_first: bool = True
    providers: list[ModelProvider] = Field(default_factory=list)

    def enabled_providers(self) -> list[ModelProvider]:
        """Return enabled providers, local providers first."""
        return sorted(self.providers, key=lambda provider: (not provider.local, provider.name))


def create_model_catalog() -> ModelCatalog:
    """Create a default model catalog aligned with README runtime options."""
    return ModelCatalog(
        providers=[
            ModelProvider(name="ollama", provider_type="local", local=True),
            ModelProvider(name="llama.cpp", provider_type="local", local=True),
            ModelProvider(name="vllm", provider_type="local", local=True),
            ModelProvider(name="huggingface", provider_type="local", local=True),
            ModelProvider(name="openai", provider_type="cloud", enabled=False, local=False),
        ]
    )
