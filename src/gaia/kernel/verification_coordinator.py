"""Independent verification of orchestration outputs before goal completion."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from gaia.orchestrator.aggregator import AggregatedResponse


class VerificationReport(BaseModel):
    """Result of verifying a kernel-managed run."""

    passed: bool
    confidence: float
    issues: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationCoordinator:
    """Verify aggregated responses using deterministic quality gates."""

    def __init__(
        self,
        *,
        min_confidence: float = 0.15,
        require_answer: bool = True,
    ) -> None:
        self.min_confidence = min_confidence
        self.require_answer = require_answer

    def verify(self, response: AggregatedResponse) -> VerificationReport:
        """Run verification checks against an aggregated orchestration response."""
        issues: list[str] = []
        checks: dict[str, bool] = {}

        status_ok = response.status in {"completed", "blocked"}
        checks["status_recognized"] = status_ok
        if not status_ok:
            issues.append(f"unrecognized response status: {response.status}")

        answer = (response.answer or "").strip()
        has_answer = bool(answer)
        checks["has_answer"] = has_answer or not self.require_answer
        if self.require_answer and not has_answer:
            issues.append("response answer is empty")

        confidence_ok = response.confidence >= self.min_confidence
        # Blocked security responses are high-confidence policy decisions.
        if response.status == "blocked":
            confidence_ok = response.confidence >= 0.5
        checks["confidence_floor"] = confidence_ok
        if not confidence_ok:
            issues.append(
                f"confidence {response.confidence:.3f} below floor "
                f"{self.min_confidence:.3f}"
            )

        agents_ok = bool(response.agents) or response.status == "blocked"
        checks["agents_present"] = agents_ok
        if not agents_ok:
            issues.append("no agent attribution present for completed run")

        pipeline = response.artifacts.get("pipeline")
        pipeline_ok = isinstance(pipeline, list) and bool(pipeline)
        checks["pipeline_artifact"] = pipeline_ok or response.status == "blocked"
        if response.status != "blocked" and not pipeline_ok:
            issues.append("missing pipeline artifact")

        passed = all(checks.values())
        return VerificationReport(
            passed=passed,
            confidence=response.confidence,
            issues=issues,
            checks=checks,
            metadata={
                "task_id": response.task_id,
                "status": response.status,
            },
        )
