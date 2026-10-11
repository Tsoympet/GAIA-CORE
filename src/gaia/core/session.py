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
        """Return an existing session, adopt an explicit id, or create one."""
        if session_id:
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing
            adopted = Session(id=session_id)
            self._sessions[adopted.id] = adopted
            return adopted
        return await self.create_session()

    def remember(self, session: Session) -> Session:
        """Keep a restored session without minting a new id."""
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Return a session by id when present."""
        return self._sessions.get(session_id)
