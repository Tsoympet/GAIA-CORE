"""Local-first AI model catalog."""

from pydantic import BaseModel, Field


class ModelProviderConfig(BaseModel):
    """Model provider configuration metadata."""

    name: str
    provider_type: str
    enabled: bool = True
    local: bool = True


class ModelCatalog(BaseModel):
    """Catalog of available model backends."""

    local_first: bool = True
    providers: list[ModelProviderConfig] = Field(default_factory=list)

    def enabled_providers(self) -> list[ModelProviderConfig]:
        """Return enabled providers, local providers first."""
        return sorted(self.providers, key=lambda provider: (not provider.local, provider.name))


def create_model_catalog() -> ModelCatalog:
    """Create a default model catalog aligned with README runtime options."""
    return ModelCatalog(
        providers=[
            ModelProviderConfig(name="ollama", provider_type="local", local=True),
            ModelProviderConfig(name="llama.cpp", provider_type="local", local=True),
            ModelProviderConfig(name="vllm", provider_type="local", local=True),
            ModelProviderConfig(name="huggingface", provider_type="local", local=True),
            ModelProviderConfig(name="openai", provider_type="cloud", enabled=False, local=False),
        ]
    )
