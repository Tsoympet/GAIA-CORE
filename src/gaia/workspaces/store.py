"""Durable local workspace persistence for GAIA Phase 4."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LINK_KINDS = frozenset({"task", "memory"})


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    """A durable workspace descriptor stored in local SQLite."""

    workspace_id: str
    name: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class WorkspaceLink:
    """A task or memory reference attached to a local workspace."""

    link_id: str
    workspace_id: str
    kind: str
    ref_id: str
    label: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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

    def attach(
        self,
        workspace_id: str,
        kind: str,
        ref_id: str,
        label: str = "",
        link_id: str | None = None,
    ) -> WorkspaceLink:
        """Attach a task or memory reference to a persisted workspace."""
        if self.get(workspace_id) is None:
            raise KeyError(workspace_id)
        cleaned_kind = kind.strip()
        cleaned_ref = ref_id.strip()
        if cleaned_kind not in LINK_KINDS:
            raise ValueError("link kind must be task or memory")
        if not cleaned_ref:
            raise ValueError("link reference must not be empty")
        now = datetime.now(UTC)
        link = WorkspaceLink(
            link_id=link_id or str(uuid4()),
            workspace_id=workspace_id,
            kind=cleaned_kind,
            ref_id=cleaned_ref,
            label=label.strip(),
            created_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_links (
                    link_id, workspace_id, kind, ref_id, label, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    link.link_id,
                    link.workspace_id,
                    link.kind,
                    link.ref_id,
                    link.label,
                    link.created_at.isoformat(),
                ),
            )
            connection.execute(
                "UPDATE workspaces SET updated_at = ? WHERE workspace_id = ?",
                (now.isoformat(), workspace_id),
            )
        return link

    def list_links(self, workspace_id: str) -> Sequence[WorkspaceLink]:
        """List task and memory references attached to one workspace."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT link_id, workspace_id, kind, ref_id, label, created_at
                FROM workspace_links
                WHERE workspace_id = ?
                ORDER BY created_at ASC, link_id ASC
                """,
                (workspace_id,),
            ).fetchall()
        return [self._link_from_row(row) for row in rows]

    def status(self) -> dict[str, Any]:
        """Return persistence status for operator APIs."""
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM workspace_links").fetchone()
        link_count = int(row["n"]) if row is not None else 0
        return {
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "workspace_count": len(self.list()),
            "link_count": link_count,
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_links (
                    link_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    ref_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workspace_links_workspace
                ON workspace_links (workspace_id, created_at)
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

    def _link_from_row(self, row: sqlite3.Row) -> WorkspaceLink:
        return WorkspaceLink(
            link_id=str(row["link_id"]),
            workspace_id=str(row["workspace_id"]),
            kind=str(row["kind"]),
            ref_id=str(row["ref_id"]),
            label=str(row["label"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
