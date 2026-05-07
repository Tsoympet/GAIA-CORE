"""Model foundation exports."""

from .catalog import ModelCatalog, ModelProviderConfig, create_model_catalog
from .cloud_client import CloudFallbackClient, CloudModelConfig
from .local_client import LocalModelClient, ModelClient
from .ollama_client import OllamaClient
from .registry import ModelDescriptor, ModelProvider, ModelRegistry
from .router import ModelRouter

__all__ = [
    "CloudFallbackClient",
    "CloudModelConfig",
    "LocalModelClient",
    "ModelCatalog",
    "ModelClient",
    "ModelDescriptor",
    "ModelProvider",
    "ModelProviderConfig",
    "ModelRegistry",
    "ModelRouter",
    "OllamaClient",
    "create_model_catalog",
]
