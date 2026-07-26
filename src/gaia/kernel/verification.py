"""Deterministic result verification for kernel-managed executions."""

from __future__ import annotations

from gaia.kernel.models import VerificationCheck, VerificationReport
from gaia.orchestrator.aggregator import AggregatedResponse


class VerificationEngine:
    """Verify structural execution invariants before accepting a result."""

    def verify(self, response: AggregatedResponse) -> VerificationReport:
        checks = [
            VerificationCheck(
                name="recognized_status",
                passed=response.status in {"completed", "blocked"},
                detail=f"response status is {response.status!r}",
            ),
            VerificationCheck(
                name="answer_present",
                passed=bool(response.answer.strip()),
                detail="response contains a non-empty answer",
            ),
            VerificationCheck(
                name="confidence_range",
                passed=0.0 <= response.confidence <= 1.0,
                detail=f"confidence is {response.confidence:.4f}",
            ),
            VerificationCheck(
                name="execution_artifacts",
                passed=(
                    response.status == "blocked"
                    or int(response.artifacts.get("node_count", 0)) > 0
                ),
                detail="completed responses must report executed nodes",
            ),
        ]
        passed = all(check.passed for check in checks)
        confidence = sum(check.passed for check in checks) / len(checks)
        return VerificationReport(
            passed=passed,
            checks=checks,
            confidence=confidence,
        )
