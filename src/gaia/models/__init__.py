"""Model foundation exports."""

from .cloud_client import CloudFallbackClient, CloudModelConfig
from .local_client import LocalModelClient, ModelClient
from .ollama_client import OllamaClient
from .registry import ModelDescriptor, ModelProvider, ModelRegistry
from .router import ModelRouter

__all__ = [
    "CloudFallbackClient", "CloudModelConfig", "LocalModelClient", "ModelClient", "ModelDescriptor",
    "ModelProvider", "ModelRegistry", "ModelRouter", "OllamaClient",
]
"""Model catalog and local-first model selection primitives."""

from gaia.models.catalog import ModelCatalog, ModelProvider, create_model_catalog

__all__ = ["ModelCatalog", "ModelProvider", "create_model_catalog"]
