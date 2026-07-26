"""Facade for scoped, symbolic, and vector-backed memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .indexer import MemoryIndexer
from .policies import MemoryPolicy
from .retriever import MemoryRetriever
from .scoped import MemoryRecord, MemoryScope, ScopedMemory
from .symbolic import SymbolicFact, SymbolicMemory
from .vector_store import InMemoryVectorStore, VectorStore


class MemoryConsent(StrEnum):
    """Consent state for owner-scoped memory operations."""

    GRANTED = "granted"
    REVOKED = "revoked"


class DeletionRequestStatus(StrEnum):
    """Review state for memory deletion requests."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class MemoryDeletionRequest:
    """Human-reviewable request to delete scoped memory."""

    owner_id: str
    scope: MemoryScope
    reason: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    status: DeletionRequestStatus = DeletionRequestStatus.PENDING
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reviewed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MemoryStatus:
    """Operational summary for Phase 4 memory and workspace readiness."""

    scopes: dict[str, int]
    indexed_documents: int
    symbolic_facts: int
    consent_records: dict[str, str]
    pending_deletion_requests: int
    retention_days: int | None
    deletion_requires_review: bool = True
    local_first: bool = True


@dataclass(slots=True)
class MemoryManager:
    """Scoped memory manager with local-first Phase 4 controls."""

    vector_store: VectorStore = field(default_factory=InMemoryVectorStore)
    symbolic: SymbolicMemory = field(default_factory=SymbolicMemory)
    policy: MemoryPolicy = field(default_factory=MemoryPolicy)
    scoped: dict[MemoryScope, ScopedMemory] = field(default_factory=dict)
    consent: dict[str, MemoryConsent] = field(default_factory=dict)
    deletion_requests: dict[str, MemoryDeletionRequest] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for scope in MemoryScope:
            self.scoped.setdefault(scope, ScopedMemory(scope=scope))

    @property
    def indexer(self) -> MemoryIndexer:
        return MemoryIndexer(self.vector_store, self.policy)

    @property
    def retriever(self) -> MemoryRetriever:
        return MemoryRetriever(self.vector_store)

    def remember(
        self,
        content: str,
        scope: MemoryScope,
        owner_id: str,
        index: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Store scoped memory only when owner consent is not revoked."""
        if self.consent.get(owner_id) == MemoryConsent.REVOKED:
            raise PermissionError(f"memory consent revoked for owner: {owner_id}")
        record_metadata = {"index": index, **(metadata or {})}
        record = self.scoped[scope].add(content, owner_id, record_metadata)
        if index:
            self.indexer.index([record])
        return record

    def grant_consent(self, owner_id: str) -> None:
        """Allow future memory writes for an owner."""
        self.consent[owner_id] = MemoryConsent.GRANTED

    def revoke_consent(self, owner_id: str) -> None:
        """Block future memory writes for an owner without deleting existing records."""
        self.consent[owner_id] = MemoryConsent.REVOKED

    def add_fact(
        self, subject: str, predicate: str, object: str, confidence: float = 1.0
    ) -> SymbolicFact:
        return self.symbolic.add(SymbolicFact(subject, predicate, object, confidence))

    def list_scope(self, scope: MemoryScope, owner_id: str) -> list[MemoryRecord]:
        """List retained records for a scope/owner after applying retention policy."""
        return [
            record
            for record in self.scoped[scope].list_for_owner(owner_id)
            if self.policy.should_keep(record)
        ]

    def export_owner(self, owner_id: str) -> dict[str, list[dict[str, Any]]]:
        """Export all retained records for an owner grouped by scope."""
        exported: dict[str, list[dict[str, Any]]] = {}
        for scope in MemoryScope:
            exported[scope.value] = [
                {
                    "record_id": record.record_id,
                    "content": record.content,
                    "metadata": record.metadata,
                    "created_at": record.created_at.isoformat(),
                }
                for record in self.list_scope(scope, owner_id)
            ]
        return exported

    def request_deletion(
        self, owner_id: str, scope: MemoryScope, reason: str
    ) -> MemoryDeletionRequest:
        """Create a deletion request; actual deletion requires approval."""
        request = MemoryDeletionRequest(owner_id=owner_id, scope=scope, reason=reason)
        self.deletion_requests[request.request_id] = request
        return request

    def review_deletion_request(self, request_id: str, approve: bool) -> MemoryDeletionRequest:
        """Approve or deny a deletion request and apply approved scope deletion."""
        request = self.deletion_requests[request_id]
        status = DeletionRequestStatus.APPROVED if approve else DeletionRequestStatus.DENIED
        reviewed = MemoryDeletionRequest(
            owner_id=request.owner_id,
            scope=request.scope,
            reason=request.reason,
            request_id=request.request_id,
            status=status,
            requested_at=request.requested_at,
            reviewed_at=datetime.now(UTC),
        )
        self.deletion_requests[request_id] = reviewed
        if approve:
            self._delete_scope_for_owner(request.scope, request.owner_id)
        return reviewed

    def status(self) -> MemoryStatus:
        """Return memory subsystem readiness and record counts."""
        pending = sum(
            1
            for request in self.deletion_requests.values()
            if request.status == DeletionRequestStatus.PENDING
        )
        return MemoryStatus(
            scopes={scope.value: len(memory.records) for scope, memory in self.scoped.items()},
            indexed_documents=len(self.vector_store.documents),
            symbolic_facts=len(self.symbolic.facts),
            consent_records={owner: state.value for owner, state in self.consent.items()},
            pending_deletion_requests=pending,
            retention_days=self.policy.retention_days,
        )

    def _delete_scope_for_owner(self, scope: MemoryScope, owner_id: str) -> None:
        scoped_memory = self.scoped[scope]
        record_ids = [
            record_id
            for record_id, record in scoped_memory.records.items()
            if record.owner_id == owner_id
        ]
        for record_id in record_ids:
            scoped_memory.records.pop(record_id, None)
        self.vector_store.delete(record_ids)
