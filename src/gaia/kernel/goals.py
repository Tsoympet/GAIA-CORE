"""Goal lifecycle management for the GAIA Cognitive Kernel."""

from __future__ import annotations

from datetime import UTC, datetime

from gaia.kernel.models import GoalRecord, GoalStatus

_ALLOWED_TRANSITIONS: dict[GoalStatus, frozenset[GoalStatus]] = {
    GoalStatus.PLANNED: frozenset(
        {GoalStatus.ACTIVE, GoalStatus.CANCELLED, GoalStatus.FAILED}
    ),
    GoalStatus.ACTIVE: frozenset(
        {GoalStatus.COMPLETED, GoalStatus.CANCELLED, GoalStatus.FAILED}
    ),
    GoalStatus.COMPLETED: frozenset(),
    GoalStatus.CANCELLED: frozenset(),
    GoalStatus.FAILED: frozenset(),
}


class GoalManager:
    """Maintain kernel goals and enforce explicit lifecycle transitions."""

    def __init__(self) -> None:
        self._goals: dict[str, GoalRecord] = {}

    def create(
        self,
        objective: str,
        *,
        priority: int = 50,
        parent_goal_id: str | None = None,
        project_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> GoalRecord:
        normalized = objective.strip()
        if not normalized:
            raise ValueError("goal objective must not be empty")
        if parent_goal_id is not None:
            self.get(parent_goal_id)
        goal = GoalRecord(
            objective=normalized,
            priority=priority,
            parent_goal_id=parent_goal_id,
            project_id=project_id,
            metadata=dict(metadata or {}),
        )
        self._goals[goal.goal_id] = goal
        return goal

    def get(self, goal_id: str) -> GoalRecord:
        try:
            return self._goals[goal_id]
        except KeyError as exc:
            raise KeyError(f"goal is not registered: {goal_id}") from exc

    def list(self, status: GoalStatus | None = None) -> list[GoalRecord]:
        goals = list(self._goals.values())
        if status is not None:
            goals = [goal for goal in goals if goal.status == status]
        return sorted(
            goals,
            key=lambda goal: (-goal.priority, goal.created_at, goal.goal_id),
        )

    def activate(self, goal_id: str) -> GoalRecord:
        return self._transition(goal_id, GoalStatus.ACTIVE)

    def complete(self, goal_id: str) -> GoalRecord:
        return self._transition(goal_id, GoalStatus.COMPLETED)

    def cancel(self, goal_id: str, reason: str | None = None) -> GoalRecord:
        return self._transition(goal_id, GoalStatus.CANCELLED, reason)

    def fail(self, goal_id: str, reason: str) -> GoalRecord:
        if not reason.strip():
            raise ValueError("goal failure reason must not be empty")
        return self._transition(goal_id, GoalStatus.FAILED, reason)

    def _transition(
        self,
        goal_id: str,
        target: GoalStatus,
        reason: str | None = None,
    ) -> GoalRecord:
        goal = self.get(goal_id)
        if target not in _ALLOWED_TRANSITIONS[goal.status]:
            raise ValueError(
                f"goal {goal_id} cannot transition from "
                f"{goal.status.value} to {target.value}"
            )
        updated = goal.model_copy(
            update={
                "status": target,
                "updated_at": datetime.now(UTC),
                "failure_reason": reason,
            }
        )
        self._goals[goal_id] = updated
        return updated
