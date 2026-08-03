"""Resource budgets and consumption tracking for kernel-managed runs."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class BudgetExceededError(RuntimeError):
    """Raised when a kernel resource budget is exhausted."""

    def __init__(self, resource: str, limit: float, used: float) -> None:
        self.resource = resource
        self.limit = limit
        self.used = used
        super().__init__(
            f"resource budget exceeded for {resource}: used={used} limit={limit}"
        )


class ResourceBudget(BaseModel):
    """Hard limits for one kernel-managed execution."""

    max_steps: int = 32
    max_model_calls: int = 16
    max_tool_calls: int = 16
    max_wall_ms: int = 120_000
    max_context_items: int = 64
    max_memory_writes: int = 128


class BudgetSnapshot(BaseModel):
    """Current consumption against a resource budget."""

    budget: ResourceBudget
    steps_used: int = 0
    model_calls_used: int = 0
    tool_calls_used: int = 0
    wall_ms_used: int = 0
    context_items_used: int = 0
    memory_writes_used: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    exhausted_resource: str | None = None

    @property
    def exhausted(self) -> bool:
        """Return whether any resource limit has been exceeded."""
        return self.exhausted_resource is not None


class ResourceBudgetTracker:
    """Track and enforce resource budgets for a single goal run."""

    def __init__(self, budget: ResourceBudget | None = None) -> None:
        self.budget = budget or ResourceBudget()
        self.snapshot = BudgetSnapshot(budget=self.budget)

    def consume(
        self,
        *,
        steps: int = 0,
        model_calls: int = 0,
        tool_calls: int = 0,
        wall_ms: int = 0,
        context_items: int = 0,
        memory_writes: int = 0,
        raise_on_exceed: bool = True,
    ) -> BudgetSnapshot:
        """Consume resources and optionally raise when a limit is exceeded."""
        self.snapshot.steps_used += steps
        self.snapshot.model_calls_used += model_calls
        self.snapshot.tool_calls_used += tool_calls
        self.snapshot.wall_ms_used += wall_ms
        self.snapshot.context_items_used += context_items
        self.snapshot.memory_writes_used += memory_writes
        self.snapshot.updated_at = datetime.now(UTC)

        checks: list[tuple[str, float, float]] = [
            ("steps", self.snapshot.steps_used, self.budget.max_steps),
            ("model_calls", self.snapshot.model_calls_used, self.budget.max_model_calls),
            ("tool_calls", self.snapshot.tool_calls_used, self.budget.max_tool_calls),
            ("wall_ms", self.snapshot.wall_ms_used, self.budget.max_wall_ms),
            (
                "context_items",
                self.snapshot.context_items_used,
                self.budget.max_context_items,
            ),
            (
                "memory_writes",
                self.snapshot.memory_writes_used,
                self.budget.max_memory_writes,
            ),
        ]
        for resource, used, limit in checks:
            if used > limit:
                self.snapshot.exhausted_resource = resource
                if raise_on_exceed:
                    raise BudgetExceededError(resource, limit, used)
                break
        return self.snapshot

    def remaining(self) -> dict[str, int]:
        """Return remaining capacity per resource."""
        return {
            "steps": max(0, self.budget.max_steps - self.snapshot.steps_used),
            "model_calls": max(
                0, self.budget.max_model_calls - self.snapshot.model_calls_used
            ),
            "tool_calls": max(
                0, self.budget.max_tool_calls - self.snapshot.tool_calls_used
            ),
            "wall_ms": max(0, self.budget.max_wall_ms - self.snapshot.wall_ms_used),
            "context_items": max(
                0, self.budget.max_context_items - self.snapshot.context_items_used
            ),
            "memory_writes": max(
                0, self.budget.max_memory_writes - self.snapshot.memory_writes_used
            ),
        }
