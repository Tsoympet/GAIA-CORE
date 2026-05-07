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


class CommandResponse(GaiaSchema):
    accepted: bool = True
    detail: str = "accepted"
    data: dict[str, Any] = Field(default_factory=dict)


class MemoryWriteRequest(GaiaSchema):
    content: str
    scope: Literal["project", "user", "session", "timeline"] = "session"
    owner_id: str = "default"


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
