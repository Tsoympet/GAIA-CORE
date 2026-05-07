"""Reflective review loop for GAIA task outputs."""

from __future__ import annotations

from pydantic import BaseModel

from gaia.metacognition.confidence_estimator import ConfidenceEstimate, ConfidenceEstimator
from gaia.metacognition.self_critique import Critique, SelfCritique


class ReflectionReport(BaseModel):
    """Combined metacognitive review report."""

    confidence: ConfidenceEstimate
    critique: Critique


class ReflectionLoop:
    """Metacognitive monitor that reviews reasoning without external action."""

    def __init__(
        self,
        estimator: ConfidenceEstimator | None = None,
        critic: SelfCritique | None = None,
    ) -> None:
        self.estimator = estimator or ConfidenceEstimator()
        self.critic = critic or SelfCritique()

    def review(self, answer: str, signals: dict[str, float]) -> ReflectionReport:
        """Run confidence estimation and self-critique."""
        estimate = self.estimator.estimate(signals)
        critique = self.critic.review(answer, estimate.confidence)
        return ReflectionReport(confidence=estimate, critique=critique)
