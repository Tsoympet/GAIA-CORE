"""Local model client protocol and deterministic echo fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ModelClient(Protocol):
    async def generate(self, prompt: str, model_id: str, **kwargs: object) -> str: ...


@dataclass(slots=True)
class LocalModelClient:
    """Placeholder for llama.cpp/vLLM/Transformers adapters."""

    async def generate(self, prompt: str, model_id: str, **kwargs: object) -> str:
        return f"[{model_id} local placeholder] {prompt}"
