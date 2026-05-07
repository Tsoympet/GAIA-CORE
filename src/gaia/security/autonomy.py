"""Autonomy limits and emergency kill-switch controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class AutonomyKillSwitch:
    enabled: bool = False
    reason: str | None = None
    triggered_at: datetime | None = None

    def trigger(self, reason: str) -> None:
        self.enabled = True
        self.reason = reason
        self.triggered_at = datetime.now(UTC)

    def reset(self) -> None:
        self.enabled = False
        self.reason = None
        self.triggered_at = None

    def require_active(self) -> None:
        if self.enabled:
            raise RuntimeError(f"autonomy disabled by kill switch: {self.reason}")


@dataclass(slots=True)
class AutonomyPolicy:
    max_steps: int = 25
    require_human_approval_for_external_effects: bool = True

    def validate_step(self, step_index: int) -> None:
        if step_index >= self.max_steps:
            raise RuntimeError(f"autonomy step limit exceeded: {self.max_steps}")
