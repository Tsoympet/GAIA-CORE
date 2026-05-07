"""Failed-problem replay for idle cognition."""

from __future__ import annotations


class ProblemReplay:
    """Replays failed tasks as internal analysis only."""

    def replay(self, failed_task: str) -> str:
        """Return an internal replay note."""
        return f"Replay analysis for failed task: {failed_task}"
