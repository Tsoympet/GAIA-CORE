"""Durable local store for symbolic facts, consent, and deletion requests.

The graph is SQLite. Confidence values and cosine scores stay uncalibrated.
No weights are downloaded.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from gaia.memory.symbolic import SymbolicFact


@dataclass(frozen=True, slots=True)
class StoredDeletion:
    """One deletion request row loaded from SQLite."""

    request_id: str
    owner_id: str
    scope: str
    reason: str
    status: str
    requested_at: datetime
    reviewed_at: datetime | None


class SQLiteFactGraph:
    """Symbolic facts, consent, and deletion requests in one SQLite file."""

    def __init__(self, db_path: Path | str = Path(".gaia/facts.sqlite3")) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def load_facts(self) -> list[SymbolicFact]:
        """Return every stored fact, including facts with no owner."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT fact_id, subject, predicate, object, confidence,
                       metadata_json, created_at
                FROM symbolic_facts
                """
            ).fetchall()
        return [_fact_from_row(row) for row in rows]

    def save_fact(self, fact: SymbolicFact) -> None:
        """Insert or replace one symbolic fact."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO symbolic_facts (
                    fact_id, subject, predicate, object, confidence,
                    metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    subject = excluded.subject,
                    predicate = excluded.predicate,
                    object = excluded.object,
                    confidence = excluded.confidence,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at
                """,
                (
                    fact.fact_id,
                    fact.subject,
                    fact.predicate,
                    fact.object,
                    fact.confidence,
                    json.dumps(fact.metadata, sort_keys=True),
                    fact.created_at.isoformat(),
                ),
            )

    def load_consent(self) -> dict[str, str]:
        """Return owner id to consent state."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT owner_id, state FROM memory_consent"
            ).fetchall()
        return {str(row["owner_id"]): str(row["state"]) for row in rows}

    def save_consent(self, owner_id: str, state: str) -> None:
        """Insert or replace one owner's consent state."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_consent (owner_id, state)
                VALUES (?, ?)
                ON CONFLICT(owner_id) DO UPDATE SET state = excluded.state
                """,
                (owner_id, state),
            )

    def load_deletions(self) -> list[StoredDeletion]:
        """Return every deletion request, pending and reviewed."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT request_id, owner_id, scope, reason, status,
                       requested_at, reviewed_at
                FROM deletion_requests
                """
            ).fetchall()
        return [_deletion_from_row(row) for row in rows]

    def save_deletion(self, deletion: StoredDeletion) -> None:
        """Insert or replace one deletion request."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO deletion_requests (
                    request_id, owner_id, scope, reason, status,
                    requested_at, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    scope = excluded.scope,
                    reason = excluded.reason,
                    status = excluded.status,
                    requested_at = excluded.requested_at,
                    reviewed_at = excluded.reviewed_at
                """,
                (
                    deletion.request_id,
                    deletion.owner_id,
                    deletion.scope,
                    deletion.reason,
                    deletion.status,
                    deletion.requested_at.isoformat(),
                    None if deletion.reviewed_at is None else deletion.reviewed_at.isoformat(),
                ),
            )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS symbolic_facts (
                    fact_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_consent (
                    owner_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS deletion_requests (
                    request_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    reviewed_at TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _fact_from_row(row: sqlite3.Row) -> SymbolicFact:
    return SymbolicFact(
        subject=str(row["subject"]),
        predicate=str(row["predicate"]),
        object=str(row["object"]),
        confidence=float(row["confidence"]),
        metadata=_object_from_json(str(row["metadata_json"])),
        fact_id=str(row["fact_id"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _deletion_from_row(row: sqlite3.Row) -> StoredDeletion:
    reviewed = row["reviewed_at"]
    return StoredDeletion(
        request_id=str(row["request_id"]),
        owner_id=str(row["owner_id"]),
        scope=str(row["scope"]),
        reason=str(row["reason"]),
        status=str(row["status"]),
        requested_at=datetime.fromisoformat(str(row["requested_at"])),
        reviewed_at=None if reviewed is None else datetime.fromisoformat(str(reviewed)),
    )


def _object_from_json(raw: str) -> dict[str, Any]:
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        return {}
    return {str(key): value for key, value in loaded.items()}
