"""In-memory + durable kernel event log with optional EventBus fan-out."""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from gaia.core.event_bus import Event, EventBus, EventDomain
from gaia.kernel.store import KernelEvent, KernelStore


class KernelEventLog:
    """Append-only kernel event log backed by the kernel store."""

    def __init__(
        self,
        store: KernelStore,
        *,
        event_bus: EventBus | None = None,
        memory_limit: int = 256,
    ) -> None:
        self.store = store
        self.event_bus = event_bus
        self._recent: deque[KernelEvent] = deque(maxlen=memory_limit)

    async def emit(
        self,
        name: str,
        *,
        goal_id: str | None = None,
        session_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> KernelEvent:
        """Persist and fan out a kernel event."""
        event = KernelEvent(
            goal_id=goal_id,
            session_id=session_id,
            name=name,
            payload=dict(payload or {}),
        )
        self.store.append_event(event)
        self._recent.append(event)
        if self.event_bus is not None:
            await self.event_bus.publish(
                Event(
                    domain=EventDomain.KERNEL,
                    name=name,
                    payload={
                        "event_id": event.id,
                        "goal_id": goal_id,
                        "session_id": session_id,
                        **event.payload,
                    },
                    trace_id=goal_id,
                )
            )
        return event

    def list_events(
        self,
        *,
        goal_id: str | None = None,
        since: datetime | None = None,
        after_id: str | None = None,
        limit: int = 100,
    ) -> list[KernelEvent]:
        """Return durable events matching the query."""
        return self.store.list_events(
            goal_id=goal_id,
            since=since,
            after_id=after_id,
            limit=limit,
        )

    def recent(self) -> list[KernelEvent]:
        """Return the recent in-memory event window."""
        return list(self._recent)

    async def stream(
        self,
        *,
        max_queue_size: int = 100,
    ) -> AsyncIterator[Event]:
        """Stream live kernel events through the shared event bus when available."""
        if self.event_bus is None:
            raise RuntimeError("kernel event streaming requires an EventBus")
        async for event in self.event_bus.stream(
            EventDomain.KERNEL,
            max_queue_size=max_queue_size,
        ):
            yield event
