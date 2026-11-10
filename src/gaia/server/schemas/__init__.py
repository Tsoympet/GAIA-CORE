"""Pydantic v2 API schemas shared by GAIA route modules."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class GaiaSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(GaiaSchema):
    status: Literal["ok"] = "ok"
    service: str = "gaia-core"


class ChatRequest(GaiaSchema):
    message: str = Field(min_length=1)
    session_id: str | None = None
    model_id: str | None = None


class ChatResponse(GaiaSchema):
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    model_id: str = ""
    provider: str = "local"
    local_fallback: bool = False
    deterministic: bool = False


class CommandResponse(GaiaSchema):
    accepted: bool = True
    detail: str = "accepted"
    data: dict[str, Any] = Field(default_factory=dict)


class MemoryWriteRequest(GaiaSchema):
    content: str
    scope: Literal["project", "user", "session", "timeline"] = "session"
    owner_id: str = "default"


class MemoryRecallRequest(GaiaSchema):
    query: str = Field(min_length=1)
    owner_id: str = "default"
    limit: int = Field(default=5, ge=1, le=20)


class MemoryRecallHit(GaiaSchema):
    record_id: str
    scope: str
    owner_id: str
    content: str
    score: float
    created_at: datetime


class MemoryRecordResponse(GaiaSchema):
    record_id: str
    scope: str
    owner_id: str
    content: str
    created_at: datetime


class ModelRegistrationRequest(GaiaSchema):
    model_id: str
    provider: Literal["ollama", "local", "cloud"] = "ollama"
    capabilities: list[str] = Field(default_factory=lambda: ["chat"])
    context_window: int | None = None
    enabled: bool = True


class SecurityDecisionResponse(GaiaSchema):
    allowed: bool
    reason: str


class PermissionCheckRequest(GaiaSchema):
    permission: str = Field(min_length=1)
    resource: str = "*"
    actor: str = "api"


class MemoryStatusResponse(GaiaSchema):
    scopes: dict[str, int]
    indexed_documents: int
    symbolic_facts: int
    consent_records: dict[str, str]
    pending_deletion_requests: int
    retention_days: int | None
    deletion_requires_review: bool = True
    local_first: bool = True


class MemoryConsentRequest(GaiaSchema):
    owner_id: str = Field(min_length=1)


class MemoryDeletionRequestCreate(GaiaSchema):
    owner_id: str = Field(min_length=1)
    scope: Literal["project", "user", "session", "timeline"]
    reason: str = Field(min_length=1)


class MemoryDeletionReviewRequest(GaiaSchema):
    approve: bool


class MemoryDeletionRequestResponse(GaiaSchema):
    request_id: str
    owner_id: str
    scope: str
    reason: str
    status: str
    requested_at: datetime
    reviewed_at: datetime | None = None


class WorkspaceCreateRequest(GaiaSchema):
    name: str = Field(min_length=1)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceResponse(GaiaSchema):
    workspace_id: str
    name: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
