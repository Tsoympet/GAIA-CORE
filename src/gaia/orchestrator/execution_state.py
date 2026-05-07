"""Runtime execution state tracking for orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .task_node import TaskNode, TaskStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class NodeExecutionRecord:
    node_id: str
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    result: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at or utc_now()
        return (end - self.started_at).total_seconds()


@dataclass(slots=True)
class ExecutionState:
    """Mutable execution ledger for a task graph run."""

    records: dict[str, NodeExecutionRecord] = field(default_factory=dict)
    cancelled: bool = False
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    @classmethod
    def from_nodes(cls, nodes: list[TaskNode]) -> "ExecutionState":
        state = cls()
        for node in nodes:
            state.records[node.id] = NodeExecutionRecord(node_id=node.id, status=node.status)
        return state

    def ensure_node(self, node_id: str) -> NodeExecutionRecord:
        return self.records.setdefault(node_id, NodeExecutionRecord(node_id=node_id))

    def start(self, node_id: str) -> None:
        record = self.ensure_node(node_id)
        record.status = TaskStatus.RUNNING
        record.attempts += 1
        record.error = None
        record.started_at = utc_now()
        record.finished_at = None

    def succeed(self, node_id: str, result: Any) -> None:
        record = self.ensure_node(node_id)
        record.status = TaskStatus.SUCCEEDED
        record.result = result
        record.error = None
        record.finished_at = utc_now()

    def fail(self, node_id: str, error: BaseException | str) -> None:
        record = self.ensure_node(node_id)
        record.status = TaskStatus.FAILED
        record.error = str(error)
        record.finished_at = utc_now()

    def skip(self, node_id: str, reason: str) -> None:
        record = self.ensure_node(node_id)
        record.status = TaskStatus.SKIPPED
        record.error = reason
        record.finished_at = utc_now()

    def cancel(self, reason: str = "execution cancelled") -> None:
        self.cancelled = True
        for record in self.records.values():
            if record.status in {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING}:
                record.status = TaskStatus.CANCELLED
                record.error = reason
                record.finished_at = utc_now()
        self.completed_at = utc_now()

    @property
    def completed_ids(self) -> set[str]:
        return {node_id for node_id, rec in self.records.items() if rec.status is TaskStatus.SUCCEEDED}

    @property
    def failed_ids(self) -> set[str]:
        return {node_id for node_id, rec in self.records.items() if rec.status is TaskStatus.FAILED}

    @property
    def is_terminal(self) -> bool:
        terminal = {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.SKIPPED}
        return bool(self.records) and all(record.status in terminal for record in self.records.values())

    def mark_complete_if_terminal(self) -> None:
        if self.is_terminal:
            self.completed_at = utc_now()
