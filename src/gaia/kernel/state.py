"""Typed Cognitive Kernel state snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class KernelStatus(StrEnum):
    """Lifecycle status for the cognitive kernel control plane."""

    IDLE = "idle"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    DEGRADED = "degraded"
    STOPPED = "stopped"


class KernelState(BaseModel):
    """Operator-visible kernel state for status APIs and diagnostics."""

    kernel_id: str = Field(default_factory=lambda: str(uuid4()))
    status: KernelStatus = KernelStatus.IDLE
    active_goal_id: str | None = None
    active_session_id: str | None = None
    goals_tracked: int = 0
    cancelled_goals: int = 0
    verified_runs: int = 0
    failed_verifications: int = 0
    budget_violations: int = 0
    interrupt_count: int = 0
    details: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def touch(
        self,
        status: KernelStatus | None = None,
        **details: object,
    ) -> None:
        """Update status/details and refresh the timestamp."""
        if status is not None:
            self.status = status
        if details:
            self.details.update(details)
        self.updated_at = datetime.now(UTC)
