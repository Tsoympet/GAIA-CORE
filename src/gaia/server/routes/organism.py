"""Memory Organism and evidence ledger API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gaia.core.runtime import GaiaRuntime
from gaia.evidence.ledger import EvidenceError
from gaia.organism.organism import MemoryCategory, MemoryOrganism, PromotionError

router = APIRouter(prefix="/organism", tags=["organism"])


class EvidenceWrite(BaseModel):
    """Append one raw evidence record."""

    source: str
    origin: str
    content: str
    producer: str
    mime_type: str = "text/plain"
    classification: str = "internal"
    execution_id: str | None = None
    license_name: str | None = None
    retention_policy: str = "keep"
    retain_until: datetime | None = None


class EpisodicWrite(BaseModel):
    """Bind an episodic-class memory to existing evidence."""

    evidence_id: str
    owner_id: str
    category: MemoryCategory = MemoryCategory.EPISODIC
    project_id: str | None = None
    sensitivity: str = "internal"
    event_at: datetime | None = None


class CandidateWrite(BaseModel):
    """Propose a cited abstraction."""

    content: str
    category: MemoryCategory
    source_memory_ids: list[str] = Field(min_length=1)
    owner_id: str
    project_id: str | None = None
    confidence: float = 0.5


class ValidationWrite(BaseModel):
    """Record validation without approving knowledge."""

    passed: bool
    notes: str = ""


class ApprovalWrite(BaseModel):
    """Approve a validated memory. This cannot change policy."""

    approver: str = "operator"


class CorrectionWrite(BaseModel):
    """Append a correction without rewriting the original."""

    content: str
    reason: str
    owner_id: str


class DeleteWrite(BaseModel):
    """Delete eligible memory text."""

    reason: str = "operator deletion"


def _unavailable() -> dict[str, object]:
    return {
        "capability": "memory_organism",
        "status": "unavailable",
        "durable": False,
        "reason": "Memory Organism is not configured for this runtime.",
    }


def _runtime(request: Request) -> GaiaRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, GaiaRuntime):
        raise HTTPException(status_code=503, detail="GAIA runtime is unavailable")
    return runtime


def _organism(request: Request) -> MemoryOrganism:
    organism = _runtime(request).organism
    if organism is None:
        raise HTTPException(status_code=409, detail=_unavailable())
    return organism


@router.get("/status")
async def organism_status(request: Request) -> dict[str, object]:
    """Report organism capability. Unconfigured runtimes are unavailable."""
    runtime = _runtime(request)
    if runtime.organism is None:
        return _unavailable()
    return runtime.organism.status()


@router.post("/evidence")
async def append_evidence(body: EvidenceWrite, request: Request) -> dict[str, object]:
    """Append raw evidence. The body is not replaced by a summary."""
    organism = _organism(request)
    try:
        record = organism.evidence.append(
            source=body.source,
            origin=body.origin,
            content=body.content,
            producer=body.producer,
            mime_type=body.mime_type,
            classification=body.classification,
            execution_id=body.execution_id,
            license_name=body.license_name,
            retention_policy=body.retention_policy,
            retain_until=body.retain_until,
        )
    except EvidenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"evidence": record.model_dump(mode="json")}


@router.get("/evidence/{evidence_id}")
async def get_evidence(evidence_id: str, request: Request) -> dict[str, object]:
    """Return one evidence record and whether its digest verifies."""
    organism = _organism(request)
    record = organism.evidence.get(evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown evidence: {evidence_id}")
    return {
        "evidence": record.model_dump(mode="json"),
        "verified": organism.evidence.verify(evidence_id),
        "cryptographic_immutability": False,
    }


@router.get("/evidence")
async def evidence_integrity(request: Request) -> dict[str, object]:
    """Verify the evidence hash chain."""
    organism = _organism(request)
    return {
        "integrity_ok": organism.evidence.verify_chain(),
        "cryptographic_immutability": False,
        "status": organism.evidence.status(),
    }


@router.post("/memories")
async def record_memory(body: EpisodicWrite, request: Request) -> dict[str, object]:
    """Record a memory that cites raw evidence."""
    organism = _organism(request)
    try:
        memory = organism.record_episodic(
            body.evidence_id,
            owner_id=body.owner_id,
            category=body.category,
            project_id=body.project_id,
            sensitivity=body.sensitivity,
            event_at=body.event_at,
        )
    except (PromotionError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"memory": memory.model_dump(mode="json")}


@router.post("/memories/candidates")
async def propose_candidate(body: CandidateWrite, request: Request) -> dict[str, object]:
    """Propose a candidate abstraction. Untrusted instructions are refused."""
    organism = _organism(request)
    try:
        memory = organism.propose_candidate(
            content=body.content,
            category=body.category,
            source_memory_ids=body.source_memory_ids,
            owner_id=body.owner_id,
            project_id=body.project_id,
            confidence=body.confidence,
        )
    except PromotionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"memory": memory.model_dump(mode="json")}


@router.post("/memories/{memory_id}/validate")
async def validate_memory(
    memory_id: str,
    body: ValidationWrite,
    request: Request,
) -> dict[str, object]:
    """Validate a candidate without approving it."""
    organism = _organism(request)
    try:
        memory = organism.validate(memory_id, passed=body.passed, notes=body.notes)
    except PromotionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"memory": memory.model_dump(mode="json")}


@router.post("/memories/{memory_id}/approve")
async def approve_memory(
    memory_id: str,
    request: Request,
    body: ApprovalWrite | None = None,
) -> dict[str, object]:
    """Approve validated knowledge. Security policy is unchanged."""
    organism = _organism(request)
    approver = body.approver if body is not None else "operator"
    try:
        memory = organism.approve(memory_id, approver)
    except PromotionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"memory": memory.model_dump(mode="json"), "policy_effect": "none"}


@router.post("/memories/{memory_id}/correct")
async def correct_memory(
    memory_id: str,
    body: CorrectionWrite,
    request: Request,
) -> dict[str, object]:
    """Append a correction and leave the original content in place."""
    organism = _organism(request)
    try:
        memory = organism.correct(
            memory_id,
            body.content,
            body.reason,
            owner_id=body.owner_id,
        )
    except PromotionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"memory": memory.model_dump(mode="json")}


@router.get("/timeline")
async def list_timeline(
    request: Request,
    owner_id: str,
    project_id: str | None = None,
) -> dict[str, object]:
    """Return recorded timeline entries in event order."""
    organism = _organism(request)
    entries = organism.list_timeline(owner_id, project_id=project_id)
    return {
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "count": len(entries),
    }


@router.get("/memories/search")
async def search_memories(
    request: Request,
    q: str = "",
    owner_id: str | None = None,
    project_id: str | None = None,
    limit: int = 10,
) -> dict[str, object]:
    """Search retained memories. Contradicted, stale, and simulation records are omitted."""
    organism = _organism(request)
    hits = organism.search(
        q,
        owner_id=owner_id,
        project_id=project_id,
        limit=limit,
    )
    return {
        "hits": [hit.model_dump(mode="json") for hit in hits],
        "count": len(hits),
    }


@router.post("/memories/{memory_id}/delete")
async def delete_memory(
    memory_id: str,
    request: Request,
    body: DeleteWrite | None = None,
) -> dict[str, object]:
    """Delete memory text. Cited evidence headers remain."""
    organism = _organism(request)
    reason = body.reason if body is not None else "operator deletion"
    try:
        memory = organism.delete(memory_id, reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "memory_id": memory.memory_id,
        "content_sha256": memory.content_sha256,
        "content_removed": memory.content is None,
        "evidence_retained": True,
    }


@router.get("/export/{owner_id}")
async def export_organism(owner_id: str, request: Request) -> dict[str, Any]:
    """Export an owner's organism memories."""
    organism = _organism(request)
    return organism.export_owner(owner_id)
