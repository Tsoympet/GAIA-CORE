"""Confidence estimation for GAIA metacognitive monitoring."""

from __future__ import annotations

from pydantic import BaseModel


class ConfidenceEstimate(BaseModel):
    """Estimated confidence and uncertainty for a task result."""

    confidence: float
    uncertainty: float
    rationale: str


class ConfidenceEstimator:
    """Heuristic confidence estimator for the bootstrap runtime."""

    def estimate(self, signals: dict[str, float]) -> ConfidenceEstimate:
        """Estimate confidence from normalized signal values."""
        if not signals:
            return ConfidenceEstimate(
                confidence=0.5, uncertainty=0.5, rationale="No signals provided."
            )
        avg = sum(max(0.0, min(1.0, value)) for value in signals.values()) / len(signals)
        return ConfidenceEstimate(
            confidence=avg,
            uncertainty=1.0 - avg,
            rationale="Mean normalized signal score.",
        )
