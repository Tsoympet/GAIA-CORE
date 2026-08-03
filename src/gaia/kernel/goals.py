"""Goal lifecycle management for the GAIA Cognitive Kernel."""

from __future__ import annotations

from datetime import UTC, datetime

from gaia.kernel.models import GoalRecord, GoalStatus
from gaia.kernel.store import InMemoryKernelStore, KernelStore

_ALLOWED_TRANSITIONS: dict[GoalStatus, frozenset[GoalStatus]] = {
    GoalStatus.PLANNED: frozenset(
        {
            GoalStatus.ACTIVE,
            GoalStatus.PAUSED,
            GoalStatus.CANCELLED,
            GoalStatus.FAILED,
        }
    ),
    GoalStatus.ACTIVE: frozenset(
        {
            GoalStatus.PAUSED,
            GoalStatus.COMPLETED,
            GoalStatus.CANCELLED,
            GoalStatus.FAILED,
        }
    ),
    GoalStatus.PAUSED: frozenset(
        {
            GoalStatus.ACTIVE,
            GoalStatus.CANCELLED,
            GoalStatus.FAILED,
        }
    ),
    GoalStatus.COMPLETED: frozenset(),
    GoalStatus.CANCELLED: frozenset(),
    GoalStatus.FAILED: frozenset(),
}


class GoalManager:
    """Maintain kernel goals and enforce explicit lifecycle transitions."""

    def __init__(self, store: KernelStore | None = None) -> None:
        self.store = store or InMemoryKernelStore()
        self._goals = {
            goal.goal_id: goal
            for goal in self.store.load_goals()
        }

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
        self.store.save_goal(goal)
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

    def pause(self, goal_id: str, reason: str | None = None) -> GoalRecord:
        return self._transition(goal_id, GoalStatus.PAUSED, reason)

    def complete(self, goal_id: str) -> GoalRecord:
        return self._transition(goal_id, GoalStatus.COMPLETED)

    def cancel(self, goal_id: str, reason: str | None = None) -> GoalRecord:
        return self._transition(goal_id, GoalStatus.CANCELLED, reason)

    def fail(self, goal_id: str, reason: str) -> GoalRecord:
        if not reason.strip():
            raise ValueError("goal failure reason must not be empty")
        return self._transition(goal_id, GoalStatus.FAILED, reason)

    def delete(self, goal_id: str) -> bool:
        goal = self.get(goal_id)
        if goal.status in {GoalStatus.ACTIVE, GoalStatus.PAUSED}:
            raise ValueError("active or paused goals cannot be deleted")
        removed = self._goals.pop(goal_id, None) is not None
        if removed:
            self.store.delete_goal(goal_id)
        return removed

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
        self.store.save_goal(updated)
        return updated
