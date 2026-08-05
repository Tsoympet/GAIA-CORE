"""Durable SQLite persistence for Cognitive Kernel state."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.kernel.goal_manager import Goal, GoalStatus

SCHEMA_VERSION = 1


class KernelEvent(BaseModel):
    """A durable, operator-visible kernel lifecycle event."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    goal_id: str | None = None
    session_id: str | None = None
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KernelStore:
    """Local-first SQLite store for goals, contexts, budgets, and events."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = Path(db_path) if db_path != ":memory:" else Path(":memory:")
        self._memory = db_path == ":memory:"
        if not self._memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Keep a long-lived connection for in-memory databases.
        self._connection: sqlite3.Connection | None = None
        if self._memory:
            self._connection = self._connect()
        self._initialize()

    def status(self) -> dict[str, object]:
        """Return persistence status for operator APIs."""
        return {
            "backend": "sqlite",
            "db_path": ":memory:" if self._memory else str(self.db_path),
            "schema_version": self.schema_version(),
            "goal_count": len(self.list_goals()),
            "event_count": self.event_count(),
            "local_first": True,
            "durable": not self._memory,
        }

    def schema_version(self) -> int:
        """Return the applied schema version."""
        with self._connect_ctx() as connection:
            row = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            ).fetchone()
        return int(row["version"]) if row is not None else 0

    def upsert_goal(self, goal: Goal) -> None:
        """Insert or update a goal record."""
        payload = (
            goal.id,
            goal.objective,
            goal.session_id,
            goal.status.value,
            json.dumps(goal.capabilities),
            goal.parent_goal_id,
            goal.created_at.isoformat(),
            goal.updated_at.isoformat(),
            goal.completed_at.isoformat() if goal.completed_at else None,
            json.dumps(goal.metadata),
            goal.error,
        )
        with self._connect_ctx() as connection:
            connection.execute(
                """
                INSERT INTO goals (
                    goal_id, objective, session_id, status, capabilities_json,
                    parent_goal_id, created_at, updated_at, completed_at,
                    metadata_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(goal_id) DO UPDATE SET
                    objective = excluded.objective,
                    session_id = excluded.session_id,
                    status = excluded.status,
                    capabilities_json = excluded.capabilities_json,
                    parent_goal_id = excluded.parent_goal_id,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at,
                    metadata_json = excluded.metadata_json,
                    error = excluded.error
                """,
                payload,
            )

    def get_goal(self, goal_id: str) -> Goal | None:
        """Load one goal by id."""
        with self._connect_ctx() as connection:
            row = connection.execute(
                """
                SELECT goal_id, objective, session_id, status, capabilities_json,
                       parent_goal_id, created_at, updated_at, completed_at,
                       metadata_json, error
                FROM goals WHERE goal_id = ?
                """,
                (goal_id,),
            ).fetchone()
        return self._goal_from_row(row) if row is not None else None

    def list_goals(
        self,
        *,
        session_id: str | None = None,
        status: GoalStatus | None = None,
    ) -> list[Goal]:
        """List persisted goals with optional filters."""
        query = """
            SELECT goal_id, objective, session_id, status, capabilities_json,
                   parent_goal_id, created_at, updated_at, completed_at,
                   metadata_json, error
            FROM goals
        """
        clauses: list[str] = []
        params: list[object] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC"
        with self._connect_ctx() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._goal_from_row(row) for row in rows]

    def save_context(
        self,
        goal_id: str,
        session_id: str,
        snapshot: dict[str, object],
    ) -> None:
        """Persist a working-context snapshot for a goal."""
        now = datetime.now(UTC).isoformat()
        with self._connect_ctx() as connection:
            connection.execute(
                """
                INSERT INTO contexts (goal_id, session_id, snapshot_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(goal_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
                """,
                (goal_id, session_id, json.dumps(snapshot), now),
            )

    def get_context(self, goal_id: str) -> dict[str, object] | None:
        """Load a persisted context snapshot."""
        with self._connect_ctx() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM contexts WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
        if row is None:
            return None
        loaded = json.loads(row["snapshot_json"])
        return loaded if isinstance(loaded, dict) else None

    def save_budget(self, goal_id: str, budget: dict[str, object]) -> None:
        """Persist a budget snapshot for a goal."""
        now = datetime.now(UTC).isoformat()
        with self._connect_ctx() as connection:
            connection.execute(
                """
                INSERT INTO budgets (goal_id, budget_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(goal_id) DO UPDATE SET
                    budget_json = excluded.budget_json,
                    updated_at = excluded.updated_at
                """,
                (goal_id, json.dumps(budget), now),
            )

    def get_budget(self, goal_id: str) -> dict[str, object] | None:
        """Load a persisted budget snapshot."""
        with self._connect_ctx() as connection:
            row = connection.execute(
                "SELECT budget_json FROM budgets WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
        if row is None:
            return None
        loaded = json.loads(row["budget_json"])
        return loaded if isinstance(loaded, dict) else None

    def append_event(self, event: KernelEvent) -> KernelEvent:
        """Append a durable kernel event."""
        with self._connect_ctx() as connection:
            connection.execute(
                """
                INSERT INTO kernel_events (
                    event_id, goal_id, session_id, name, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.goal_id,
                    event.session_id,
                    event.name,
                    json.dumps(event.payload),
                    event.created_at.isoformat(),
                ),
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
        """List kernel events in chronological order."""
        query = """
            SELECT event_id, goal_id, session_id, name, payload_json, created_at
            FROM kernel_events
        """
        clauses: list[str] = []
        params: list[object] = []
        if goal_id is not None:
            clauses.append("goal_id = ?")
            params.append(goal_id)
        if since is not None:
            clauses.append("created_at > ?")
            params.append(since.isoformat())
        if after_id is not None:
            clauses.append(
                "created_at > COALESCE("
                "(SELECT created_at FROM kernel_events WHERE event_id = ?), '')"
            )
            params.append(after_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC, event_id ASC LIMIT ?"
        params.append(max(1, limit))
        with self._connect_ctx() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._event_from_row(row) for row in rows]

    def event_count(self) -> int:
        """Return the number of stored kernel events."""
        with self._connect_ctx() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM kernel_events").fetchone()
        return int(row["n"]) if row is not None else 0

    def close(self) -> None:
        """Close the long-lived in-memory connection when present."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _initialize(self) -> None:
        with self._connect_ctx() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            row = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            ).fetchone()
            current = int(row["version"]) if row is not None else 0
            if current < 1:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS goals (
                        goal_id TEXT PRIMARY KEY,
                        objective TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        capabilities_json TEXT NOT NULL,
                        parent_goal_id TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        completed_at TEXT,
                        metadata_json TEXT NOT NULL,
                        error TEXT
                    );
                    CREATE TABLE IF NOT EXISTS contexts (
                        goal_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        snapshot_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS budgets (
                        goal_id TEXT PRIMARY KEY,
                        budget_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS kernel_events (
                        event_id TEXT PRIMARY KEY,
                        goal_id TEXT,
                        session_id TEXT,
                        name TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_goals_session
                        ON goals(session_id);
                    CREATE INDEX IF NOT EXISTS idx_goals_status
                        ON goals(status);
                    CREATE INDEX IF NOT EXISTS idx_events_created
                        ON kernel_events(created_at);
                    CREATE INDEX IF NOT EXISTS idx_events_goal
                        ON kernel_events(goal_id, created_at);
                    """
                )
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (1, datetime.now(UTC).isoformat()),
                )

    def _connect(self) -> sqlite3.Connection:
        target = ":memory:" if self._memory else str(self.db_path)
        connection = sqlite3.connect(target, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connect_ctx(self) -> Iterator[sqlite3.Connection]:
        if self._connection is not None:
            try:
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            return

        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _goal_from_row(self, row: sqlite3.Row) -> Goal:
        completed_raw = row["completed_at"]
        return Goal(
            id=row["goal_id"],
            objective=row["objective"],
            session_id=row["session_id"],
            status=GoalStatus(row["status"]),
            capabilities=list(json.loads(row["capabilities_json"])),
            parent_goal_id=row["parent_goal_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=(
                datetime.fromisoformat(completed_raw) if completed_raw else None
            ),
            metadata=dict(json.loads(row["metadata_json"])),
            error=row["error"],
        )

    def _event_from_row(self, row: sqlite3.Row) -> KernelEvent:
        return KernelEvent(
            id=row["event_id"],
            goal_id=row["goal_id"],
            session_id=row["session_id"],
            name=row["name"],
            payload=dict(json.loads(row["payload_json"])),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
