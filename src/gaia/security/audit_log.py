"""Append-only audit logging primitives for security-sensitive actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


class AuditOutcome(StrEnum):
    """Outcome recorded for a guarded action."""

    ALLOWED = "allowed"
    DENIED = "denied"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Structured audit event emitted by guards and managers."""

    action: str
    actor: str
    outcome: AuditOutcome
    reason: str | None = None
    resource: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_json(self) -> str:
        payload = asdict(self)
        payload["outcome"] = self.outcome.value
        payload["created_at"] = self.created_at.isoformat()
        return json.dumps(payload, sort_keys=True)


class AuditLog:
    """Small append-only JSONL audit log suitable for local-first deployments."""

    def __init__(self, path: Path | str = ".gaia/audit/security.jsonl") -> None:
        self.path = Path(path)
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._events.append(event)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(event.to_json() + "\n")
        return event

    def recent(self, limit: int = 100) -> list[AuditEvent]:
        with self._lock:
            return list(self._events[-limit:])
