"""Asynchronous event bus for GAIA runtime domains."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class EventDomain(StrEnum):
    """Supported event domains emitted by the core runtime."""

    TASK = "task"
    AGENT = "agent"
    RUNTIME = "runtime"
    MEMORY = "memory"
    SECURITY = "security"


@dataclass(frozen=True, slots=True)
class Event:
    """A structured runtime event."""

    domain: EventDomain
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


EventHandler = Callable[[Event], Any]
SubscriptionToken = str


class EventBus:
    """Small async publish/subscribe bus with domain and wildcard listeners."""

    WILDCARD = "*"

    def __init__(self) -> None:
        self._subscribers: dict[str, dict[SubscriptionToken, EventHandler]] = defaultdict(dict)
        self._lock = asyncio.Lock()
        self._closed = False

    async def subscribe(
        self,
        domain: EventDomain | str,
        handler: EventHandler,
    ) -> SubscriptionToken:
        """Subscribe a callback to a domain or ``*`` and return an unsubscribe token."""

        self._ensure_open()
        key = self._key(domain)
        token = str(uuid4())
        async with self._lock:
            self._subscribers[key][token] = handler
        return token

    async def unsubscribe(self, token: SubscriptionToken) -> bool:
        """Remove a subscription token from all domains."""

        async with self._lock:
            for handlers in self._subscribers.values():
                if token in handlers:
                    del handlers[token]
                    return True
        return False

    async def publish(self, event: Event) -> None:
        """Publish an event and await all currently registered handlers."""

        self._ensure_open()
        handlers = await self._matching_handlers(event.domain)
        if not handlers:
            return
        results = [handler(event) for handler in handlers]
        await asyncio.gather(
            *(result for result in results if hasattr(result, "__await__")),
            return_exceptions=False,
        )

    async def stream(
        self,
        domain: EventDomain | str = WILDCARD,
        *,
        max_queue_size: int = 100,
    ) -> AsyncIterator[Event]:
        """Create an async iterator that yields events for a domain."""

        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)

        async def enqueue(event: Event) -> None:
            await queue.put(event)

        token = await self.subscribe(domain, enqueue)
        try:
            while True:
                yield await queue.get()
        finally:
            await self.unsubscribe(token)

    async def close(self) -> None:
        """Close the bus and remove all subscriptions."""

        async with self._lock:
            self._closed = True
            self._subscribers.clear()

    async def _matching_handlers(self, domain: EventDomain) -> list[EventHandler]:
        keys = (self._key(domain), self.WILDCARD)
        async with self._lock:
            return [handler for key in keys for handler in self._subscribers.get(key, {}).values()]

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("event bus is closed")

    def _key(self, domain: EventDomain | str) -> str:
        if isinstance(domain, EventDomain):
            return domain.value
        if domain == self.WILDCARD:
            return self.WILDCARD
        return EventDomain(domain).value


async def publish_many(event_bus: EventBus, events: Iterable[Event]) -> None:
    """Publish a sequence of events in order."""

    for event in events:
        await event_bus.publish(event)
