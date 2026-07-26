"""Typed state models for the GAIA Cognitive Kernel."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class GoalStatus(StrEnum):
    """Lifecycle states for a kernel-managed goal."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ExecutionStatus(StrEnum):
    """Lifecycle states for a kernel-managed task execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"
    INTERRUPTED = "interrupted"


class ResourceBudget(BaseModel):
    """Hard resource limits attached to one execution."""

    max_seconds: float | None = Field(default=None, gt=0)
    max_steps: int | None = Field(default=None, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, ge=0)


class ResourceUsage(BaseModel):
    """Measured resource usage for one execution."""

    elapsed_seconds: float = Field(default=0.0, ge=0)
    steps: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)


class VerificationCheck(BaseModel):
    """One deterministic kernel verification check."""

    name: str
    passed: bool
    detail: str


class VerificationReport(BaseModel):
    """Post-execution verification result."""

    passed: bool
    checks: list[VerificationCheck] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class KernelStorageStatus(BaseModel):
    """Operator-facing status for kernel persistence."""

    backend: str
    durable: bool
    location: str | None = None
    schema_version: int = Field(ge=0)
    goals: int = Field(default=0, ge=0)
    executions: int = Field(default=0, ge=0)


class GoalRecord(BaseModel):
    """Kernel-owned goal state."""

    goal_id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str = Field(min_length=1)
    status: GoalStatus = GoalStatus.PLANNED
    priority: int = Field(default=50, ge=0, le=100)
    parent_goal_id: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    failure_reason: str | None = None


class KernelExecution(BaseModel):
    """Kernel ledger entry for one runtime task."""

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    objective: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    goal_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    budget: ResourceBudget = Field(default_factory=ResourceBudget)
    usage: ResourceUsage = Field(default_factory=ResourceUsage)
    verification: VerificationReport | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class KernelStatus(BaseModel):
    """Operator-facing kernel status."""

    state: str = "ready"
    goals: int = 0
    active_goals: int = 0
    executions: int = 0
    active_executions: int = 0
    cancellation_requests: int = 0
    recovered_interruptions: int = 0
    storage: KernelStorageStatus = Field(
        default_factory=lambda: KernelStorageStatus(
            backend="memory",
            durable=False,
            schema_version=1,
        )
    )
