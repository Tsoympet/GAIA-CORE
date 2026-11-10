"""Deterministic local model client used when no weights are loaded."""

from __future__ import annotations

from typing import Protocol

DETERMINISTIC_MODEL_ID = "gaia-deterministic-local"


class ModelClient(Protocol):
    """Async text generation client used by the model router."""

    async def generate(self, prompt: str, model_id: str, **kwargs: object) -> str: ...

_STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "also",
        "and",
        "because",
        "before",
        "from",
        "have",
        "into",
        "that",
        "the",
        "this",
        "with",
        "your",
    }
)


class LocalModelClient:
    """Local-first answerer that does not download or call a model.

    The client is intentionally deterministic. It plans from the operator text
    and states its limits. It is the working path when Ollama is absent.
    """

    model_id = DETERMINISTIC_MODEL_ID

    async def generate(self, prompt: str, model_id: str, **kwargs: object) -> str:
        del kwargs
        return self.compose(prompt, model_id or self.model_id)

    def compose(self, prompt: str, model_id: str) -> str:
        """Build a structured local plan from the prompt."""
        objective = " ".join(prompt.split())
        if not objective:
            raise ValueError("prompt must not be empty")
        focus = ", ".join(self._focus_terms(objective))
        return "\n".join(
            [
                "GAIA local deterministic client",
                f"model_id: {model_id}",
                "provider: local",
                "neural_weights_loaded: false",
                "cloud_fallback: disabled",
                f"objective: {objective}",
                f"focus: {focus}",
                "constraints:",
                "- Stay on this machine. Do not call a paid cloud model.",
                "- Risky actions stay behind an explicit human approval.",
                "- Voice output stays synthetic and must not impersonate a real person.",
                "steps:",
                "1. Restate the objective under the local-only constraint.",
                "2. Select a registered specialist for the focus terms.",
                "3. Return a structured result the operator can review.",
                "4. Write memory only when that owner has not revoked consent.",
                "result:",
                f"Prepared a local plan for: {objective}",
            ]
        )

    def health(self) -> dict[str, object]:
        """Report the deterministic client as available."""
        return {
            "provider": "local",
            "model_id": self.model_id,
            "available": True,
            "deterministic": True,
            "neural_weights_loaded": False,
            "detail": (
                "Deterministic local client is the working path when Ollama "
                "has no ready model."
            ),
        }

    def _focus_terms(self, objective: str) -> list[str]:
        terms: list[str] = []
        for raw in objective.split():
            word = raw.strip(".,:;!?()[]\"'").lower()
            if len(word) <= 3 or word in _STOP_WORDS or word in terms:
                continue
            terms.append(word)
            if len(terms) == 6:
                break
        return terms or ["stated-objective"]
