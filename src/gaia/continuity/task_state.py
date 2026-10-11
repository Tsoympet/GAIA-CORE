"""Validated task lifecycle for kernel-managed work."""

from __future__ import annotations

from enum import StrEnum


class TaskState(StrEnum):
    """Persistent lifecycle for one kernel task run."""

    CREATED = "created"
    CLASSIFIED = "classified"
    PLANNED = "planned"
    APPROVED_IF_REQUIRED = "approved_if_required"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    WAITING_FOR_USER = "waiting_for_user"
    CANCELLED = "cancelled"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    ROLLED_BACK = "rolled_back"
    INTERRUPTED = "interrupted"


TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.CREATED: frozenset(
        {
            TaskState.CLASSIFIED,
            TaskState.PLANNED,
            TaskState.BLOCKED,
            TaskState.WAITING_FOR_USER,
            TaskState.CANCELLED,
            TaskState.FAILED,
            TaskState.INTERRUPTED,
            TaskState.QUARANTINED,
        }
    ),
    TaskState.CLASSIFIED: frozenset(
        {
            TaskState.PLANNED,
            TaskState.EXECUTING,
            TaskState.BLOCKED,
            TaskState.WAITING_FOR_USER,
            TaskState.CANCELLED,
            TaskState.FAILED,
            TaskState.INTERRUPTED,
            TaskState.QUARANTINED,
        }
    ),
    TaskState.PLANNED: frozenset(
        {
            TaskState.APPROVED_IF_REQUIRED,
            TaskState.EXECUTING,
            TaskState.BLOCKED,
            TaskState.WAITING_FOR_USER,
            TaskState.CANCELLED,
            TaskState.FAILED,
            TaskState.INTERRUPTED,
        }
    ),
    TaskState.APPROVED_IF_REQUIRED: frozenset(
        {
            TaskState.EXECUTING,
            TaskState.WAITING_FOR_USER,
            TaskState.BLOCKED,
            TaskState.CANCELLED,
            TaskState.FAILED,
            TaskState.INTERRUPTED,
        }
    ),
    TaskState.EXECUTING: frozenset(
        {
            TaskState.VERIFYING,
            TaskState.FAILED,
            TaskState.INTERRUPTED,
            TaskState.CANCELLED,
            TaskState.BLOCKED,
            TaskState.QUARANTINED,
        }
    ),
    TaskState.VERIFYING: frozenset(
        {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.BLOCKED,
            TaskState.ROLLED_BACK,
            TaskState.INTERRUPTED,
        }
    ),
    TaskState.INTERRUPTED: frozenset(
        {
            TaskState.CLASSIFIED,
            TaskState.PLANNED,
            TaskState.CANCELLED,
            TaskState.FAILED,
            TaskState.QUARANTINED,
            TaskState.ROLLED_BACK,
            TaskState.WAITING_FOR_USER,
        }
    ),
    TaskState.WAITING_FOR_USER: frozenset(
        {
            TaskState.APPROVED_IF_REQUIRED,
            TaskState.CANCELLED,
            TaskState.BLOCKED,
            TaskState.FAILED,
        }
    ),
    TaskState.BLOCKED: frozenset(
        {
            TaskState.WAITING_FOR_USER,
            TaskState.CANCELLED,
            TaskState.ROLLED_BACK,
        }
    ),
    TaskState.FAILED: frozenset({TaskState.ROLLED_BACK, TaskState.QUARANTINED}),
    TaskState.COMPLETED: frozenset(),
    TaskState.CANCELLED: frozenset(),
    TaskState.QUARANTINED: frozenset({TaskState.ROLLED_BACK}),
    TaskState.ROLLED_BACK: frozenset(),
}

class TaskTransitionError(ValueError):
    """Raised when a task state change is not in the allowed graph."""

    def __init__(self, from_state: TaskState, to_state: TaskState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"illegal task transition: {from_state.value} -> {to_state.value}"
        )


TERMINAL_STATES: frozenset[TaskState] = frozenset(
    {
        TaskState.COMPLETED,
        TaskState.CANCELLED,
        TaskState.ROLLED_BACK,
    }
)

UNSAFE_RECOVERY_STATES: frozenset[TaskState] = frozenset(
    {
        TaskState.EXECUTING,
        TaskState.VERIFYING,
    }
)


def validate_transition(from_state: TaskState, to_state: TaskState) -> None:
    """Reject a task transition that the lifecycle does not allow."""
    if from_state == to_state:
        return
    if to_state not in TRANSITIONS[from_state]:
        raise TaskTransitionError(from_state, to_state)
