"""Typed task node models for GAIA orchestration.

The models in this module are intentionally lightweight and dependency-free so
that the orchestrator can run in local-first environments before optional
runtime packages are installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class TaskStatus(str, Enum):
    """Lifecycle states for a task node."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry behavior for a task node.

    Attributes:
        max_attempts: Total number of attempts, including the first attempt.
        backoff_seconds: Initial delay before retrying a failed task.
        backoff_multiplier: Multiplier applied to the delay after each failure.
        retry_on_timeout: Whether timeout failures should be retried.
    """

    max_attempts: int = 1
    backoff_seconds: float = 0.0
    backoff_multiplier: float = 2.0
    retry_on_timeout: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """Capability requirements used by the router to choose an executor."""

    capabilities: frozenset[str] = field(default_factory=frozenset)
    preferred_kind: str | None = None
    constraints: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_values(
        cls,
        capabilities: Sequence[str] | None = None,
        *,
        preferred_kind: str | None = None,
        constraints: Mapping[str, Any] | None = None,
    ) -> "CapabilityRequirement":
        return cls(
            capabilities=frozenset(capabilities or ()),
            preferred_kind=preferred_kind,
            constraints=dict(constraints or {}),
        )


@dataclass(slots=True)
class TaskNode:
    """A single unit of planned work in the orchestration DAG."""

    id: str
    description: str
    dependencies: set[str] = field(default_factory=set)
    capability: CapabilityRequirement = field(default_factory=CapabilityRequirement)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: float | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("task node id is required")
        if not self.description:
            raise ValueError("task node description is required")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when provided")
        self.dependencies = set(self.dependencies)
        if self.id in self.dependencies:
            raise ValueError(f"task node {self.id!r} cannot depend on itself")

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.SKIPPED,
        }

    def copy_for_execution(self) -> "TaskNode":
        """Return a mutable execution copy without sharing dependency metadata."""

        return TaskNode(
            id=self.id,
            description=self.description,
            dependencies=set(self.dependencies),
            capability=self.capability,
            retry_policy=self.retry_policy,
            timeout_seconds=self.timeout_seconds,
            status=self.status,
            result=self.result,
            metadata=dict(self.metadata),
        )
