"""No-action guard for GAIA idle cognition."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class IdleOperation(StrEnum):
    """Allowed idle cognition operation classes."""

    ANALYZE = "analyze"
    SUMMARIZE = "summarize"
    SIMULATE = "simulate"
    WRITE_INTERNAL_NOTE = "write_internal_note"


class NoActionDecision(BaseModel):
    """Decision for a proposed idle cognition operation."""

    allowed: bool
    reason: str


class NoActionGuard:
    """Ensures idle cognition never performs external actions."""

    allowed_operations = {operation.value for operation in IdleOperation}

    def check(self, operation: str) -> NoActionDecision:
        """Allow only analysis, summary, simulation, and internal notes."""
        if operation in self.allowed_operations:
            return NoActionDecision(allowed=True, reason="safe internal idle cognition operation")
        return NoActionDecision(
            allowed=False, reason="idle cognition may not execute external actions"
        )

    def require(self, operation: str) -> None:
        """Raise when an idle operation would perform external action."""
        decision = self.check(operation)
        if not decision.allowed:
            raise PermissionError(decision.reason)
