"""Goal and task-state management for the Cognitive Kernel."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class GoalStatus(StrEnum):
    """Lifecycle states for a kernel-managed goal."""

    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class Goal(BaseModel):
    """A user or system objective tracked by the kernel."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    session_id: str
    status: GoalStatus = GoalStatus.PENDING
    capabilities: list[str] = Field(default_factory=list)
    parent_goal_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)


class GoalManager:
    """In-memory goal registry with deterministic lifecycle transitions."""

    _TERMINAL: frozenset[GoalStatus] = frozenset(
        {
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
            GoalStatus.BLOCKED,
        }
    )

    def __init__(self) -> None:
        self._goals: dict[str, Goal] = {}

    def load(self, goals: list[Goal]) -> None:
        """Hydrate the registry from durable storage."""
        for goal in goals:
            self._goals[goal.id] = goal

    def create(
        self,
        objective: str,
        session_id: str,
        *,
        capabilities: list[str] | None = None,
        parent_goal_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        goal_id: str | None = None,
    ) -> Goal:
        """Create and register a pending goal."""
        goal = Goal(
            id=goal_id or str(uuid4()),
            objective=objective,
            session_id=session_id,
            capabilities=list(capabilities or []),
            parent_goal_id=parent_goal_id,
            metadata=dict(metadata or {}),
        )
        self._goals[goal.id] = goal
        return goal

    def get(self, goal_id: str) -> Goal | None:
        """Return a goal by id, or ``None`` if unknown."""
        return self._goals.get(goal_id)

    def require(self, goal_id: str) -> Goal:
        """Return a goal or raise ``KeyError`` when missing."""
        goal = self.get(goal_id)
        if goal is None:
            raise KeyError(f"unknown goal: {goal_id}")
        return goal

    def list_goals(
        self,
        *,
        session_id: str | None = None,
        status: GoalStatus | None = None,
    ) -> list[Goal]:
        """List goals, optionally filtered by session or status."""
        goals = list(self._goals.values())
        if session_id is not None:
            goals = [goal for goal in goals if goal.session_id == session_id]
        if status is not None:
            goals = [goal for goal in goals if goal.status == status]
        return sorted(goals, key=lambda goal: goal.created_at)

    def activate(self, goal_id: str) -> Goal:
        """Mark a pending or interrupted goal as active."""
        goal = self.require(goal_id)
        if goal.status not in {GoalStatus.PENDING, GoalStatus.INTERRUPTED}:
            raise RuntimeError(
                f"goal {goal_id} cannot activate from status {goal.status.value}"
            )
        goal.status = GoalStatus.ACTIVE
        goal._touch()
        return goal

    def complete(self, goal_id: str, *, metadata: dict[str, Any] | None = None) -> Goal:
        """Mark a goal completed."""
        return self._finish(goal_id, GoalStatus.COMPLETED, metadata=metadata)

    def fail(
        self,
        goal_id: str,
        error: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        """Mark a goal failed with an error reason."""
        goal = self._finish(goal_id, GoalStatus.FAILED, metadata=metadata)
        goal.error = error
        goal._touch()
        return goal

    def block(
        self,
        goal_id: str,
        reason: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        """Mark a goal blocked (typically by policy)."""
        goal = self._finish(goal_id, GoalStatus.BLOCKED, metadata=metadata)
        goal.error = reason
        goal._touch()
        return goal

    def cancel(self, goal_id: str, reason: str = "cancelled") -> Goal:
        """Cancel a non-terminal goal."""
        goal = self.require(goal_id)
        if goal.status in self._TERMINAL:
            raise RuntimeError(
                f"goal {goal_id} already terminal with status {goal.status.value}"
            )
        goal.status = GoalStatus.CANCELLED
        goal.error = reason
        goal.completed_at = datetime.now(UTC)
        goal._touch()
        return goal

    def interrupt(self, goal_id: str, reason: str = "interrupted") -> Goal:
        """Mark an active goal as interrupted for safe stop/resume."""
        goal = self.require(goal_id)
        if goal.status == GoalStatus.INTERRUPTED:
            goal.error = reason
            goal._touch()
            return goal
        if goal.status != GoalStatus.ACTIVE:
            raise RuntimeError(
                f"goal {goal_id} cannot interrupt from status {goal.status.value}"
            )
        goal.status = GoalStatus.INTERRUPTED
        goal.error = reason
        goal._touch()
        return goal

    def remove(self, goal_id: str) -> Goal | None:
        """Remove a goal from the live registry."""
        return self._goals.pop(goal_id, None)

    def clear(self) -> None:
        """Remove all goals from the live registry."""
        self._goals.clear()

    def count(self) -> int:
        """Return the number of tracked goals."""
        return len(self._goals)

    def count_by_status(self, status: GoalStatus) -> int:
        """Count goals in a given status."""
        return sum(1 for goal in self._goals.values() if goal.status == status)

    def _finish(
        self,
        goal_id: str,
        status: GoalStatus,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        goal = self.require(goal_id)
        if goal.status in self._TERMINAL:
            raise RuntimeError(
                f"goal {goal_id} already terminal with status {goal.status.value}"
            )
        goal.status = status
        if metadata:
            goal.metadata.update(metadata)
        goal.completed_at = datetime.now(UTC)
        goal._touch()
        return goal
