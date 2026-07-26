"""Ollama-first local model client."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class OllamaClient:
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 120.0

    async def generate(
        self,
        prompt: str,
        model_id: str,
        **kwargs: object,
    ) -> str:
        payload = {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
            **kwargs,
        }
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", ""))
