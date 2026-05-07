"""Base abstractions for GAIA agents.

The classes in this module provide a small, dependency-free contract for
capability-driven, permission-aware agent execution. Concrete agents should
subclass :class:`BaseAgent`, declare immutable metadata, and return an
:class:`AgentResult` from their async ``execute`` method.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, Sequence


class AgentStatus(StrEnum):
    """Structured execution states returned by agents."""

    SUCCESS = "success"
    FAILURE = "failure"
    PERMISSION_DENIED = "permission_denied"


class Permission(StrEnum):
    """Known security permissions that agents may require."""

    READ_CONTEXT = "read_context"
    WRITE_CONTEXT = "write_context"
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    NETWORK_ACCESS = "network_access"
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    CODE_EXECUTION = "code_execution"
    SECURITY_REVIEW = "security_review"
    SYSTEM_INTROSPECTION = "system_introspection"
    SELF_MODEL_READ = "self_model_read"
    METACOGNITION = "metacognition"
    DREAMING = "dreaming"
    HUMAN_APPROVAL = "human_approval"


@dataclass(frozen=True, slots=True)
class AgentMetadata:
    """Descriptive metadata advertised by an agent."""

    name: str
    description: str
    version: str = "0.1.0"
    owner: str = "gaia"
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    """Structured context supplied to an agent for one execution."""

    task: str
    inputs: Mapping[str, Any] = field(default_factory=dict)
    granted_permissions: frozenset[Permission] = field(default_factory=frozenset)
    session_id: str | None = None
    user_id: str | None = None
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Structured result returned by every GAIA agent."""

    agent_name: str
    status: AgentStatus
    output: Mapping[str, Any] = field(default_factory=dict)
    capability: str | None = None
    trace_id: str | None = None
    error: str | None = None
    required_permissions: tuple[Permission, ...] = field(default_factory=tuple)
    missing_permissions: tuple[Permission, ...] = field(default_factory=tuple)
    started_at: float = field(default_factory=time.time)
    completed_at: float = field(default_factory=time.time)

    @property
    def duration_seconds(self) -> float:
        """Return wall-clock duration for this execution result."""

        return max(0.0, self.completed_at - self.started_at)


class AgentPermissionError(PermissionError):
    """Raised when an agent is executed without required permissions."""

    def __init__(self, missing_permissions: Sequence[Permission]) -> None:
        self.missing_permissions = tuple(missing_permissions)
        permissions = ", ".join(permission.value for permission in self.missing_permissions)
        super().__init__(f"Missing required agent permissions: {permissions}")


class BaseAgent(ABC):
    """Abstract base class for capability-routed GAIA agents."""

    metadata: ClassVar[AgentMetadata]
    capabilities: ClassVar[frozenset[str]] = frozenset()
    required_permissions: ClassVar[frozenset[Permission]] = frozenset({Permission.READ_CONTEXT})

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(f"gaia.agents.{self.metadata.name}")

    def can_handle(self, capability: str) -> bool:
        """Return whether this agent advertises a capability."""

        return capability in self.capabilities

    def missing_permissions(self, context: AgentExecutionContext) -> tuple[Permission, ...]:
        """Return required permissions that are absent from the execution context."""

        return tuple(
            permission
            for permission in sorted(self.required_permissions, key=lambda value: value.value)
            if permission not in context.granted_permissions
        )

    def ensure_permissions(self, context: AgentExecutionContext) -> None:
        """Raise :class:`AgentPermissionError` when required permissions are absent."""

        missing = self.missing_permissions(context)
        if missing:
            self.log_event(
                "permission_denied",
                context,
                missing_permissions=[permission.value for permission in missing],
            )
            raise AgentPermissionError(missing)

    def permission_denied_result(
        self,
        context: AgentExecutionContext,
        started_at: float,
        missing_permissions: Sequence[Permission],
        capability: str | None = None,
    ) -> AgentResult:
        """Build a structured permission-denied result."""

        return AgentResult(
            agent_name=self.metadata.name,
            status=AgentStatus.PERMISSION_DENIED,
            capability=capability,
            trace_id=context.trace_id,
            error="Permission denied",
            required_permissions=tuple(sorted(self.required_permissions, key=lambda value: value.value)),
            missing_permissions=tuple(missing_permissions),
            started_at=started_at,
            completed_at=time.time(),
        )

    def success_result(
        self,
        context: AgentExecutionContext,
        started_at: float,
        output: Mapping[str, Any],
        capability: str | None = None,
    ) -> AgentResult:
        """Build a structured success result."""

        return AgentResult(
            agent_name=self.metadata.name,
            status=AgentStatus.SUCCESS,
            output=MappingProxyType(dict(output)),
            capability=capability,
            trace_id=context.trace_id,
            required_permissions=tuple(sorted(self.required_permissions, key=lambda value: value.value)),
            started_at=started_at,
            completed_at=time.time(),
        )

    def failure_result(
        self,
        context: AgentExecutionContext,
        started_at: float,
        error: str,
        capability: str | None = None,
        output: Mapping[str, Any] | None = None,
    ) -> AgentResult:
        """Build a structured failure result."""

        return AgentResult(
            agent_name=self.metadata.name,
            status=AgentStatus.FAILURE,
            output=MappingProxyType(dict(output or {})),
            capability=capability,
            trace_id=context.trace_id,
            error=error,
            required_permissions=tuple(sorted(self.required_permissions, key=lambda value: value.value)),
            started_at=started_at,
            completed_at=time.time(),
        )

    def log_event(self, event: str, context: AgentExecutionContext, **fields: Any) -> None:
        """Emit structured log fields for observability and audit trails."""

        self.logger.info(
            event,
            extra={
                "gaia_event": event,
                "agent_name": self.metadata.name,
                "trace_id": context.trace_id,
                "session_id": context.session_id,
                "user_id": context.user_id,
                **fields,
            },
        )

    @abstractmethod
    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        """Execute the agent asynchronously and return a structured result."""
