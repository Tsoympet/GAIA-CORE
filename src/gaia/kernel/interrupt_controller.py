"""Cancellation and interruption control for kernel-managed goals."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class InterruptKind(StrEnum):
    """Kinds of interrupt that can stop a running goal."""

    CANCEL = "cancel"
    PREEMPT = "preempt"
    BUDGET = "budget"
    KILL_SWITCH = "kill_switch"
    OPERATOR = "operator"


class InterruptRequest(BaseModel):
    """A recorded interrupt request for a goal."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    goal_id: str
    kind: InterruptKind = InterruptKind.CANCEL
    reason: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    acknowledged: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterruptController:
    """Track per-goal and global interrupt requests."""

    def __init__(self) -> None:
        self._by_goal: dict[str, InterruptRequest] = {}
        self._global: InterruptRequest | None = None
        self._history: list[InterruptRequest] = []

    def request(
        self,
        goal_id: str,
        reason: str,
        *,
        kind: InterruptKind = InterruptKind.CANCEL,
        metadata: dict[str, Any] | None = None,
    ) -> InterruptRequest:
        """Request interruption of a specific goal."""
        interrupt = InterruptRequest(
            goal_id=goal_id,
            kind=kind,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        self._by_goal[goal_id] = interrupt
        self._history.append(interrupt)
        return interrupt

    def request_global(
        self,
        reason: str,
        *,
        kind: InterruptKind = InterruptKind.OPERATOR,
        metadata: dict[str, Any] | None = None,
    ) -> InterruptRequest:
        """Request interruption of all active goals."""
        interrupt = InterruptRequest(
            goal_id="*",
            kind=kind,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        self._global = interrupt
        self._history.append(interrupt)
        return interrupt

    def is_interrupted(self, goal_id: str) -> bool:
        """Return whether a goal (or all goals) should stop."""
        if self._global is not None:
            return True
        return goal_id in self._by_goal

    def get(self, goal_id: str) -> InterruptRequest | None:
        """Return the pending interrupt for a goal, preferring global."""
        if self._global is not None:
            return self._global
        return self._by_goal.get(goal_id)

    def acknowledge(self, goal_id: str) -> InterruptRequest | None:
        """Acknowledge and clear a goal interrupt after safe stop."""
        interrupt = self._by_goal.pop(goal_id, None)
        if interrupt is not None:
            interrupt.acknowledged = True
        return interrupt

    def clear_global(self) -> None:
        """Clear a global interrupt latch."""
        self._global = None

    def history(self) -> list[InterruptRequest]:
        """Return interrupt history in request order."""
        return list(self._history)

    def pending_count(self) -> int:
        """Return the number of pending goal interrupts plus global latch."""
        return len(self._by_goal) + (1 if self._global is not None else 0)
