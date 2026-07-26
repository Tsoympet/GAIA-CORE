"""Durable and in-memory stores for Cognitive Kernel state."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from gaia.kernel.models import (
    GoalRecord,
    KernelExecution,
    KernelStorageStatus,
)

CURRENT_SCHEMA_VERSION = 1


class KernelStore(Protocol):
    """Persistence contract for kernel-owned goals and executions."""

    def save_goal(self, goal: GoalRecord) -> None: ...

    def save_execution(self, execution: KernelExecution) -> None: ...

    def load_goals(self) -> list[GoalRecord]: ...

    def load_executions(self) -> list[KernelExecution]: ...

    def delete_goal(self, goal_id: str) -> bool: ...

    def delete_execution(self, execution_id: str) -> bool: ...

    def status(self) -> KernelStorageStatus: ...

    def backup_to(self, destination: Path | str) -> Path: ...


@dataclass(slots=True)
class InMemoryKernelStore:
    """Process-local store used when durability is not configured."""

    goals: dict[str, GoalRecord] = field(default_factory=dict)
    executions: dict[str, KernelExecution] = field(default_factory=dict)

    def save_goal(self, goal: GoalRecord) -> None:
        self.goals[goal.goal_id] = goal.model_copy(deep=True)

    def save_execution(self, execution: KernelExecution) -> None:
        self.executions[execution.execution_id] = execution.model_copy(deep=True)

    def load_goals(self) -> list[GoalRecord]:
        return [goal.model_copy(deep=True) for goal in self.goals.values()]

    def load_executions(self) -> list[KernelExecution]:
        return [
            execution.model_copy(deep=True)
            for execution in self.executions.values()
        ]

    def delete_goal(self, goal_id: str) -> bool:
        return self.goals.pop(goal_id, None) is not None

    def delete_execution(self, execution_id: str) -> bool:
        return self.executions.pop(execution_id, None) is not None

    def status(self) -> KernelStorageStatus:
        return KernelStorageStatus(
            backend="memory",
            durable=False,
            schema_version=CURRENT_SCHEMA_VERSION,
            goals=len(self.goals),
            executions=len(self.executions),
        )

    def backup_to(self, destination: Path | str) -> Path:
        raise RuntimeError("in-memory kernel state cannot be backed up")


class SQLiteKernelStore:
    """Versioned SQLite store with atomic goal and execution upserts."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_goal(self, goal: GoalRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO kernel_goals(goal_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(goal_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    goal.goal_id,
                    goal.model_dump_json(),
                    goal.updated_at.isoformat(),
                ),
            )

    def save_execution(self, execution: KernelExecution) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO kernel_executions(
                    execution_id,
                    goal_id,
                    status,
                    payload_json,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    goal_id = excluded.goal_id,
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    execution.execution_id,
                    execution.goal_id,
                    execution.status.value,
                    execution.model_dump_json(),
                    self._execution_timestamp(execution),
                ),
            )

    def load_goals(self) -> list[GoalRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM kernel_goals ORDER BY updated_at, goal_id"
            ).fetchall()
        return [GoalRecord.model_validate_json(row[0]) for row in rows]

    def load_executions(self) -> list[KernelExecution]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM kernel_executions
                ORDER BY updated_at, execution_id
                """
            ).fetchall()
        return [KernelExecution.model_validate_json(row[0]) for row in rows]

    def delete_goal(self, goal_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM kernel_goals WHERE goal_id = ?",
                (goal_id,),
            )
            removed = cursor.rowcount > 0
        return removed

    def delete_execution(self, execution_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM kernel_executions WHERE execution_id = ?",
                (execution_id,),
            )
            removed = cursor.rowcount > 0
        return removed

    def status(self) -> KernelStorageStatus:
        with self._connect() as connection:
            schema_version = self._schema_version(connection)
            goals = int(
                connection.execute(
                    "SELECT COUNT(*) FROM kernel_goals"
                ).fetchone()[0]
            )
            executions = int(
                connection.execute(
                    "SELECT COUNT(*) FROM kernel_executions"
                ).fetchone()[0]
            )
        return KernelStorageStatus(
            backend="sqlite",
            durable=True,
            location=str(self.path),
            schema_version=schema_version,
            goals=goals,
            executions=executions,
        )

    def backup_to(self, destination: Path | str) -> Path:
        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as source:
            with sqlite3.connect(target) as backup:
                source.backup(backup)
        return target

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS kernel_schema (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    version INTEGER NOT NULL
                )
                """
            )
            version = self._schema_version(connection)
            if version > CURRENT_SCHEMA_VERSION:
                raise RuntimeError(
                    f"kernel database schema {version} is newer than "
                    f"supported version {CURRENT_SCHEMA_VERSION}"
                )
            if version < 1:
                self._migrate_to_v1(connection)

    def _migrate_to_v1(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS kernel_goals (
                goal_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS kernel_executions (
                execution_id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS ix_kernel_executions_goal
                ON kernel_executions(goal_id);
            CREATE INDEX IF NOT EXISTS ix_kernel_executions_status
                ON kernel_executions(status);

            INSERT INTO kernel_schema(singleton, version)
            VALUES (1, 1)
            ON CONFLICT(singleton) DO UPDATE SET version = excluded.version;
            """
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            with connection:
                yield connection
        finally:
            connection.close()

    def _schema_version(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT version FROM kernel_schema WHERE singleton = 1"
        ).fetchone()
        return 0 if row is None else int(row[0])

    @staticmethod
    def _execution_timestamp(execution: KernelExecution) -> str:
        timestamp = (
            execution.finished_at
            or execution.started_at
            or execution.created_at
        )
        return timestamp.isoformat()
