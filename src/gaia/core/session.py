"""User session models and management for GAIA Core."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class Session:
    """Represents one authenticated or anonymous user interaction session."""

    user_id: str
    session_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    active: bool = True

    def touch(self) -> None:
        """Refresh the session activity timestamp."""

        self.updated_at = datetime.now(UTC)

    def close(self) -> None:
        """Mark the session inactive."""

        self.active = False
        self.touch()


class SessionManager:
    """In-memory session registry used by the core runtime."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        user_id: str = "anonymous",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        session = Session(user_id=user_id, metadata=metadata or {})
        async with self._lock:
            self._sessions[session.session_id] = session
        return session

    async def get_session(self, session_id: str) -> Session | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.touch()
            return session

    async def require_session(self, session_id: str) -> Session:
        session = await self.get_session(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        return session

    async def close_session(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.close()
            return True

    async def list_sessions(self, *, include_inactive: bool = False) -> list[Session]:
        async with self._lock:
            return [
                session
                for session in self._sessions.values()
                if include_inactive or session.active
            ]
