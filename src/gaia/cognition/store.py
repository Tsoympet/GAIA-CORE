"""Durable local journal for phase-4, dream, and metacognition notes.

The dream engine does not write this file. API routes append notes after an
internal cycle. Nothing in this store launches a shell, network call, or
project-file edit.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

NOTE_KINDS = frozenset({"phase4", "dream", "idle", "metacognition"})


@dataclass(frozen=True, slots=True)
class CognitionNote:
    """One journal row stored in local SQLite."""

    note_id: str
    kind: str
    body: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CognitionNoteStore:
    """Sibling `.gaia` SQLite file for notes that must survive a restart."""

    def __init__(self, db_path: Path | str = Path(".gaia/cognition.sqlite3")) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def append(
        self,
        kind: str,
        body: str,
        payload: dict[str, Any] | None = None,
    ) -> CognitionNote:
        """Append one note. `kind` is a closed set of internal journals."""
        cleaned_kind = kind.strip()
        if cleaned_kind not in NOTE_KINDS:
            raise ValueError(f"unsupported cognition note kind: {kind}")
        note = CognitionNote(
            note_id=str(uuid4()),
            kind=cleaned_kind,
            body=body,
            payload=payload or {},
            created_at=datetime.now(UTC),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cognition_notes (
                    note_id, kind, body, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    note.note_id,
                    note.kind,
                    note.body,
                    json.dumps(note.payload, sort_keys=True),
                    note.created_at.isoformat(),
                ),
            )
        return note

    def list_notes(
        self,
        kind: str | None = None,
        *,
        owner_id: str | None = None,
        limit: int = 50,
    ) -> list[CognitionNote]:
        """Return newest notes first.

        When `owner_id` is set, notes without that owner are omitted. Dream
        and metacognition rows have no owner and stay out of an owner filter.
        """
        if limit < 1:
            raise ValueError("limit must be positive")
        query = """
            SELECT note_id, kind, body, payload_json, created_at
            FROM cognition_notes
        """
        clauses: list[str] = []
        params: list[object] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if owner_id is not None:
            clauses.append("json_extract(payload_json, '$.owner_id') = ?")
            params.append(owner_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC, note_id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def latest(self, kind: str) -> CognitionNote | None:
        """Return the newest note of one kind, if any."""
        notes = self.list_notes(kind, limit=1)
        return notes[0] if notes else None

    def status(self) -> dict[str, Any]:
        """Return journal readiness without executing an external action."""
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM cognition_notes").fetchone()
        return {
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "note_count": int(row["n"]) if row is not None else 0,
            "kinds": sorted(NOTE_KINDS),
            "local_first": True,
            "durable": True,
            "external_actions": False,
        }

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cognition_notes (
                    note_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    body TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cognition_notes_kind
                ON cognition_notes (kind, created_at)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _from_row(self, row: sqlite3.Row) -> CognitionNote:
        loaded = json.loads(str(row["payload_json"]))
        payload = loaded if isinstance(loaded, dict) else {}
        return CognitionNote(
            note_id=str(row["note_id"]),
            kind=str(row["kind"]),
            body=str(row["body"]),
            payload=payload,
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )


def note_strings(payload: dict[str, Any]) -> list[str]:
    """Read a stored list of dream or idle note strings."""
    raw = payload.get("notes")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]
