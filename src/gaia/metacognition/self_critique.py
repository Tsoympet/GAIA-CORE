"""Self-critique utilities for reflective review."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Critique(BaseModel):
    """Structured critique of a task result."""

    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class SelfCritique:
    """Rule-based task self-evaluation helper."""

    def review(self, answer: str, confidence: float) -> Critique:
        """Review a response for uncertainty and completeness signals."""
        risks: list[str] = []
        suggestions: list[str] = []
        if confidence < 0.7:
            risks.append("Confidence is below the preferred autonomous threshold.")
            suggestions.append("Ask for clarification or route to a stronger specialist/model.")
        if len(answer.strip()) < 20:
            risks.append("Answer is very short and may be incomplete.")
        return Critique(
            strengths=["Structured response produced."],
            risks=risks,
            improvement_suggestions=suggestions,
        )
