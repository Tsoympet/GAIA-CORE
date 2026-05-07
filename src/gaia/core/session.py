"""Session primitives for GAIA runtime requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Session(BaseModel):
    """A user or workspace execution session."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "anonymous"
    workspace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionManager:
    """In-memory session manager for the first runnable GAIA core."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def create_session(
        self,
        user_id: str = "anonymous",
        *,
        workspace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Create and store a new session."""
        session = Session(user_id=user_id, workspace_id=workspace_id, metadata=metadata or {})
        self._sessions[session.id] = session
        return session

    async def get_or_create(self, session_id: str | None = None) -> Session:
        """Return an existing session or create an anonymous one."""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return await self.create_session()

    def get(self, session_id: str) -> Session | None:
        """Return a session by id when present."""
        return self._sessions.get(session_id)
