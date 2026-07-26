"""Cooperative cancellation registry for kernel executions."""

from __future__ import annotations

import asyncio


class CancellationRegistry:
    """Track cancellation events without exposing mutable task internals."""

    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._reasons: dict[str, str] = {}

    def register(self, execution_id: str) -> asyncio.Event:
        if execution_id in self._events:
            raise ValueError(
                f"cancellation token already exists: {execution_id}"
            )
        event = asyncio.Event()
        self._events[execution_id] = event
        return event

    def request(self, execution_id: str, reason: str) -> None:
        if not reason.strip():
            raise ValueError("cancellation reason must not be empty")
        event = self.get(execution_id)
        self._reasons[execution_id] = reason
        event.set()

    def get(self, execution_id: str) -> asyncio.Event:
        try:
            return self._events[execution_id]
        except KeyError as exc:
            raise KeyError(
                f"cancellation token is not registered: {execution_id}"
            ) from exc

    def is_requested(self, execution_id: str) -> bool:
        return self.get(execution_id).is_set()

    def reason(self, execution_id: str) -> str | None:
        return self._reasons.get(execution_id)

    def remove(self, execution_id: str) -> None:
        self._events.pop(execution_id, None)
        self._reasons.pop(execution_id, None)

    def requested_count(self) -> int:
        return sum(event.is_set() for event in self._events.values())
