"""Goal rehearsal for future planning simulation."""

from __future__ import annotations


class GoalRehearsal:
    """Rehearses possible plans without executing them."""

    def rehearse(self, goal: str) -> list[str]:
        """Return safe internal rehearsal steps."""
        return [
            f"Clarify goal: {goal}",
            "Identify required capabilities.",
            "Check permissions before any future external action.",
        ]
