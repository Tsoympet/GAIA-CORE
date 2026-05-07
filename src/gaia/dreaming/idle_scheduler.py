"""Idle scheduler for safe non-autonomous cognition cycles."""

from __future__ import annotations

from gaia.dreaming.no_action_guard import NoActionGuard


class IdleScheduler:
    """Runs only explicit, internal idle cognition cycles."""

    def __init__(self, guard: NoActionGuard | None = None) -> None:
        self.guard = guard or NoActionGuard()

    def can_run_cycle(self) -> bool:
        """Return whether an internal simulation cycle may run."""
        return self.guard.check("simulate").allowed
