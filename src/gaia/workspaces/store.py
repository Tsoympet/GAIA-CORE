"""Durable local workspace persistence for GAIA Phase 4."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    """A durable workspace descriptor stored in local SQLite."""

    workspace_id: str
    name: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SQLiteWorkspaceStore:
    """Small local-first SQLite store for workspace lifecycle metadata."""

    def __init__(self, db_path: Path | str = Path(".gaia/workspaces.sqlite3")) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
        workspace_id: str | None = None,
    ) -> WorkspaceRecord:
        """Create and persist a workspace record."""
        now = datetime.now(UTC)
        record = WorkspaceRecord(
            workspace_id=workspace_id or str(uuid4()),
            name=name.strip(),
            description=description,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        if not record.name:
            raise ValueError("workspace name must not be empty")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id, name, description, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                self._to_row(record),
            )
        return record

    def list(self) -> list[WorkspaceRecord]:
        """List persisted workspaces in creation order."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT workspace_id, name, description, metadata_json, created_at, updated_at
                FROM workspaces
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, workspace_id: str) -> WorkspaceRecord | None:
        """Return one workspace or None when it is not persisted."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT workspace_id, name, description, metadata_json, created_at, updated_at
                FROM workspaces
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def status(self) -> dict[str, Any]:
        """Return persistence status for operator APIs."""
        return {
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "workspace_count": len(self.list()),
            "local_first": True,
            "durable": True,
        }

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _to_row(self, record: WorkspaceRecord) -> tuple[str, str, str, str, str, str]:
        return (
            record.workspace_id,
            record.name,
            record.description,
            json.dumps(record.metadata, sort_keys=True),
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )

    def _from_row(self, row: sqlite3.Row) -> WorkspaceRecord:
        return WorkspaceRecord(
            workspace_id=str(row["workspace_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            metadata=json.loads(str(row["metadata_json"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )
