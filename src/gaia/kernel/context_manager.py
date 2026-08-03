"""Working-context management with size limits for the Cognitive Kernel."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ContextItem(BaseModel):
    """One keyed item in a goal's working context."""

    key: str
    value: object
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = Field(default_factory=list)


class WorkingContext(BaseModel):
    """Bounded working context bound to a goal and session."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    goal_id: str
    session_id: str
    items: list[ContextItem] = Field(default_factory=list)
    max_items: int = 64
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def size(self) -> int:
        """Return the number of retained context items."""
        return len(self.items)


class ContextManager:
    """Manage per-goal working contexts with deterministic eviction."""

    def __init__(self, *, default_max_items: int = 64) -> None:
        self.default_max_items = default_max_items
        self._contexts: dict[str, WorkingContext] = {}

    def bind(
        self,
        goal_id: str,
        session_id: str,
        *,
        max_items: int | None = None,
    ) -> WorkingContext:
        """Create or return the working context for a goal."""
        existing = self._contexts.get(goal_id)
        if existing is not None:
            return existing
        context = WorkingContext(
            goal_id=goal_id,
            session_id=session_id,
            max_items=max_items if max_items is not None else self.default_max_items,
        )
        self._contexts[goal_id] = context
        return context

    def get(self, goal_id: str) -> WorkingContext | None:
        """Return the working context for a goal, if present."""
        return self._contexts.get(goal_id)

    def put(
        self,
        goal_id: str,
        key: str,
        value: object,
        *,
        tags: list[str] | None = None,
    ) -> WorkingContext:
        """Upsert a context item and enforce the item budget."""
        context = self._contexts.get(goal_id)
        if context is None:
            raise KeyError(f"no working context for goal: {goal_id}")

        context.items = [item for item in context.items if item.key != key]
        context.items.append(
            ContextItem(key=key, value=value, tags=list(tags or []))
        )
        overflow = len(context.items) - context.max_items
        if overflow > 0:
            context.items = context.items[overflow:]
        context.updated_at = datetime.now(UTC)
        return context

    def get_value(self, goal_id: str, key: str) -> object | None:
        """Return a context value by key, or ``None``."""
        context = self._contexts.get(goal_id)
        if context is None:
            return None
        for item in reversed(context.items):
            if item.key == key:
                return item.value
        return None

    def snapshot(self, goal_id: str) -> dict[str, object]:
        """Return a JSON-serializable snapshot of a working context."""
        context = self._contexts.get(goal_id)
        if context is None:
            return {}
        return context.model_dump(mode="json")

    def release(self, goal_id: str) -> None:
        """Drop a working context when a goal terminates."""
        self._contexts.pop(goal_id, None)

    def active_count(self) -> int:
        """Return the number of active working contexts."""
        return len(self._contexts)
