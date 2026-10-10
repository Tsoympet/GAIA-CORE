"""Structured errors for the cognitive continuity journal."""

from __future__ import annotations

from gaia.continuity.task_state import TaskTransitionError

__all__ = [
    "ContinuityIntegrityError",
    "ContinuityLockedError",
    "TaskTransitionError",
]


class ContinuityIntegrityError(RuntimeError):
    """Raised when a checkpoint or schema operation fails verification."""


class ContinuityLockedError(RuntimeError):
    """Raised when another live process holds the continuity journal lock."""

    def __init__(self, holder: str) -> None:
        self.holder = holder
        super().__init__(
            "continuity journal is locked by live process "
            f"{holder}; recovery will not interrupt it"
        )
