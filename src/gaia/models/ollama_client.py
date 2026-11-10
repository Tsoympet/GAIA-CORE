"""Ollama-first local model client."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class OllamaClient:
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 120.0
    health_timeout_seconds: float = 0.4

    async def health(self) -> dict[str, object]:
        """Probe the local daemon without waiting on a long generation."""
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.health_timeout_seconds,
            ) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            return {
                "provider": "ollama",
                "available": False,
                "reachable": False,
                "models": [],
                "detail": type(exc).__name__,
            }
        names: list[str] = []
        if isinstance(payload, dict):
            listed = payload.get("models", [])
            if isinstance(listed, list):
                for item in listed:
                    if isinstance(item, dict) and isinstance(item.get("name"), str):
                        names.append(item["name"])
        return {
            "provider": "ollama",
            "available": True,
            "reachable": True,
            "models": names,
            "detail": "ok",
        }

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
