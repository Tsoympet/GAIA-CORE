"""Deterministic result verification for kernel-managed executions."""

from __future__ import annotations

from gaia.kernel.models import VerificationCheck, VerificationReport
from gaia.orchestrator.aggregator import AggregatedResponse


def _artifact_integer(value: object) -> int:
    """Return an integer artifact value without unsafe coercion."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


class VerificationEngine:
    """Verify structural execution invariants before accepting a result."""

    def verify(self, response: AggregatedResponse) -> VerificationReport:
        node_count = _artifact_integer(
            response.artifacts.get("node_count", 0)
        )
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
                passed=response.status == "blocked" or node_count > 0,
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
