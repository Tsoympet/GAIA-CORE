"""Durable Memory Organism over the local evidence ledger.

Promotion is explicit:

raw evidence → episodic record → candidate abstraction → validation → approved
long-term knowledge.

Simulation records and untrusted instruction-like text cannot become approved
factual knowledge. Approval never changes security policy.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from gaia.continuity.records import Checkpoint
from gaia.continuity.store import ContinuityStore
from gaia.evidence.codec import canonical_json, sha256_text
from gaia.evidence.ledger import EvidenceLedger
from gaia.organism.binding import (
    CHECKPOINT_ORIGIN,
    CHECKPOINT_PRODUCER,
    checkpoint_evidence_content,
)
from gaia.organism.guards import (
    UNTRUSTED_SOURCES,
    looks_like_untrusted_instruction,
    redact_assignments,
)
from gaia.organism.retrieval import bm25_scores
from gaia.security.field_cipher import (
    DataKeyError,
    FieldCipher,
    open_field,
    seal_field,
    seal_if_plain,
)

SCHEMA_VERSION = 1

ORGANISM_SQL = """
CREATE TABLE IF NOT EXISTS organism_schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organism_memories (
    memory_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    project_id TEXT,
    confidence REAL NOT NULL,
    confidence_basis TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    approved_knowledge INTEGER NOT NULL,
    policy_effect TEXT NOT NULL,
    untrusted_instruction INTEGER NOT NULL,
    source_evidence_json TEXT NOT NULL,
    source_memory_json TEXT NOT NULL,
    parent_memory_id TEXT,
    valid_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organism_events (
    event_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organism_contradictions (
    contradiction_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    other_memory_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

DROP_ORGANISM_V1 = """
DROP TABLE IF EXISTS organism_contradictions;
DROP TABLE IF EXISTS organism_events;
DROP TABLE IF EXISTS organism_memories;
"""


class MemoryCategory(StrEnum):
    """Distinct memory classes. They are not interchangeable."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    CORRECTION = "correction"
    PROJECT = "project"
    SIMULATION = "simulation"
    AUTOBIOGRAPHICAL = "autobiographical"


class MemoryStatus(StrEnum):
    """Lifecycle state for one organism memory."""

    RECORDED = "recorded"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONTRADICTED = "contradicted"
    DELETED = "deleted"


class PromotionError(ValueError):
    """Raised when a memory transition is not allowed."""


class OrganismMemory(BaseModel):
    """One persisted organism memory."""

    memory_id: str
    category: MemoryCategory
    status: MemoryStatus
    content: str | None
    content_sha256: str
    owner_id: str
    project_id: str | None = None
    confidence: float
    confidence_basis: str
    sensitivity: str
    approved_knowledge: bool = False
    policy_effect: str = "none"
    untrusted_instruction: bool = False
    source_evidence_ids: list[str] = Field(default_factory=list)
    source_memory_ids: list[str] = Field(default_factory=list)
    parent_memory_id: str | None = None
    valid_until: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @property
    def effective_status(self) -> str:
        """Return stale when a validity instant has passed."""
        if (
            self.status not in {MemoryStatus.DELETED, MemoryStatus.REJECTED}
            and self.valid_until is not None
            and self.valid_until <= datetime.now(UTC)
        ):
            return "stale"
        return self.status.value


class RetrievalHit(BaseModel):
    """One ranked memory returned by local retrieval."""

    memory: OrganismMemory
    score: float
    effective_status: str


class MemoryOrganism:
    """Local durable memory organism and its evidence ledger."""

    def __init__(self, db_path: Path | str, *, cipher: FieldCipher | None = None) -> None:
        self.db_path = Path(db_path)
        self.cipher = cipher
        self.evidence = EvidenceLedger(self.db_path, cipher=cipher)
        self.continuity_bound = False
        self.migrate()
        if cipher is not None:
            self.reseal_plaintext()

    def migrate(self) -> int:
        """Apply the organism schema."""
        with self._transaction() as connection:
            _execute_sql_script(connection, ORGANISM_SQL)
            row = connection.execute(
                "SELECT MAX(version) AS version FROM organism_schema_migrations"
            ).fetchone()
            current = 0 if row is None or row["version"] is None else int(row["version"])
            if current < 1:
                connection.execute(
                    """
                    INSERT INTO organism_schema_migrations (version, name, applied_at)
                    VALUES (1, 'organism_initial', ?)
                    """,
                    (_now().isoformat(),),
                )
                current = 1
            if current > SCHEMA_VERSION:
                raise PromotionError(
                    f"organism schema {current} is newer than this build ({SCHEMA_VERSION})"
                )
            return current

    def reseal_plaintext(self) -> int:
        """Encrypt plaintext memory text in place. Content digests stay plaintext hashes."""
        if self.cipher is None:
            return 0
        changed = 0
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT memory_id, content FROM organism_memories"
            ).fetchall()
            for row in rows:
                sealed = seal_if_plain(self.cipher, str(row["content"]))
                if sealed is None:
                    continue
                connection.execute(
                    "UPDATE organism_memories SET content = ? WHERE memory_id = ?",
                    (sealed, str(row["memory_id"])),
                )
                changed += 1
        return changed

    def rollback_schema(self, target: int, *, force: bool = False) -> int:
        """Drop organism tables back to version 0 when forced.

        Evidence headers and continuity tables in the same file are kept.
        """
        if target < 0 or target > SCHEMA_VERSION:
            raise ValueError(f"unsupported organism schema target: {target}")
        self.migrate()
        with self._transaction() as connection:
            current = _organism_schema_version(connection)
            if target > current:
                raise ValueError("schema rollback target is newer than the applied version")
            if target == current:
                return current
            count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM organism_memories"
            ).fetchone()
            memory_count = 0 if count_row is None else int(count_row["count"])
            if memory_count and not force:
                raise PromotionError(
                    "schema rollback would drop organism memories; pass force=True"
                )
            if target == 0 and current >= 1:
                _execute_sql_script(connection, DROP_ORGANISM_V1)
                connection.execute("DELETE FROM organism_schema_migrations WHERE version >= 1")
            return _organism_schema_version(connection)

    def record_episodic(
        self,
        evidence_id: str,
        *,
        owner_id: str,
        category: MemoryCategory = MemoryCategory.EPISODIC,
        project_id: str | None = None,
        sensitivity: str = "internal",
        valid_until: datetime | None = None,
        confidence: float = 1.0,
    ) -> OrganismMemory:
        """Bind a memory to raw evidence without replacing that evidence."""
        evidence = self.evidence.get(evidence_id)
        if evidence is None or evidence.content_text is None:
            raise PromotionError(f"evidence is missing or purged: {evidence_id}")
        if category not in {
            MemoryCategory.EPISODIC,
            MemoryCategory.WORKING,
            MemoryCategory.AUTOBIOGRAPHICAL,
            MemoryCategory.PROJECT,
            MemoryCategory.SIMULATION,
        }:
            raise PromotionError("direct records must start as episodic-class memories")
        untrusted = evidence.source in UNTRUSTED_SOURCES and looks_like_untrusted_instruction(
            evidence.content_text
        )
        return self._insert(
            category=category,
            status=MemoryStatus.RECORDED,
            content=evidence.content_text,
            owner_id=owner_id,
            project_id=project_id,
            confidence=confidence,
            confidence_basis="evidence",
            sensitivity=sensitivity,
            approved_knowledge=False,
            untrusted_instruction=untrusted,
            source_evidence_ids=[evidence_id],
            source_memory_ids=[],
            parent_memory_id=None,
            valid_until=valid_until,
            event_type="recorded",
            event_detail={"evidence_id": evidence_id},
        )

    def record_kernel_outcome(
        self,
        *,
        objective: str,
        answer: str,
        status: str,
        session_id: str,
        execution_id: str,
        project_id: str | None = None,
    ) -> OrganismMemory:
        """Record a kernel outcome as evidence plus autobiographical memory."""
        body = redact_assignments(
            f"objective: {objective}\nstatus: {status}\nanswer: {answer}"
        )
        evidence = self.evidence.append(
            source="system",
            origin=f"kernel-session:{session_id}",
            content=body,
            producer="cognitive_kernel",
            execution_id=execution_id,
            classification="internal",
        )
        return self.record_episodic(
            evidence.evidence_id,
            owner_id=session_id,
            category=MemoryCategory.AUTOBIOGRAPHICAL,
            project_id=project_id,
        )

    def record_checkpoint_evidence(self, checkpoint: Checkpoint) -> bool:
        """Cite a published checkpoint by digest. Returns whether a row was added.

        The checkpoint payload is not read and is not stored.
        """
        if checkpoint.publication != "published":
            raise PromotionError("only published checkpoints can be cited as evidence")
        for record in self.evidence.list_records():
            same_checkpoint = record.execution_id == checkpoint.checkpoint_id
            if same_checkpoint and record.origin == CHECKPOINT_ORIGIN:
                return False
        content = checkpoint_evidence_content(checkpoint)
        self.evidence.append(
            source="system",
            origin=CHECKPOINT_ORIGIN,
            content=content,
            producer=CHECKPOINT_PRODUCER,
            mime_type="application/json",
            classification="internal",
            execution_id=checkpoint.checkpoint_id,
            relationship="checkpoint-digest",
        )
        return True

    def bind_continuity(self, store: ContinuityStore) -> int:
        """Backfill published checkpoints and cite later publications."""
        added = 0
        for checkpoint in store.list_checkpoints():
            if self.record_checkpoint_evidence(checkpoint):
                added += 1

        def _witness(checkpoint: Checkpoint) -> None:
            self.record_checkpoint_evidence(checkpoint)

        store.checkpoint_witness = _witness
        self.continuity_bound = True
        return added

    def propose_candidate(
        self,
        *,
        content: str,
        category: MemoryCategory,
        source_memory_ids: list[str],
        owner_id: str,
        project_id: str | None = None,
        confidence: float = 0.5,
    ) -> OrganismMemory:
        """Propose an abstraction that cites existing memories."""
        if category not in {
            MemoryCategory.SEMANTIC,
            MemoryCategory.PROCEDURAL,
            MemoryCategory.PROJECT,
            MemoryCategory.SIMULATION,
        }:
            raise PromotionError("candidates must name a long-term category")
        if not source_memory_ids:
            raise PromotionError("a candidate must cite at least one source memory")
        if not content.strip():
            raise PromotionError("candidate content must not be empty")
        sources = [self.require(memory_id) for memory_id in source_memory_ids]
        if any(source.untrusted_instruction for source in sources):
            raise PromotionError(
                "untrusted instruction-like content cannot become a candidate"
            )
        if any(source.status is MemoryStatus.DELETED for source in sources):
            raise PromotionError("deleted memory cannot support a candidate")
        if category is not MemoryCategory.SIMULATION and any(
            source.category is MemoryCategory.SIMULATION for source in sources
        ):
            raise PromotionError("simulation memory cannot be promoted into factual knowledge")
        if looks_like_untrusted_instruction(content):
            raise PromotionError("instruction-like text cannot be proposed as knowledge")
        evidence_ids: list[str] = []
        for source in sources:
            for evidence_id in source.source_evidence_ids:
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)
        return self._insert(
            category=category,
            status=MemoryStatus.CANDIDATE,
            content=content,
            owner_id=owner_id,
            project_id=project_id,
            confidence=_bounded(confidence),
            confidence_basis="unspecified",
            sensitivity="internal",
            approved_knowledge=False,
            untrusted_instruction=False,
            source_evidence_ids=evidence_ids,
            source_memory_ids=list(source_memory_ids),
            parent_memory_id=source_memory_ids[0],
            valid_until=None,
            event_type="candidate",
            event_detail={"source_memory_ids": list(source_memory_ids)},
        )

    def validate(self, memory_id: str, *, passed: bool, notes: str) -> OrganismMemory:
        """Record an independent validation result. This does not approve knowledge."""
        memory = self.require(memory_id)
        if memory.status is not MemoryStatus.CANDIDATE:
            raise PromotionError("only candidates can be validated")
        status = MemoryStatus.VALIDATED if passed else MemoryStatus.REJECTED
        self._set_status(memory_id, status, "validated" if passed else "rejected", {"notes": notes})
        return self.require(memory_id)

    def approve(self, memory_id: str, approver: str) -> OrganismMemory:
        """Approve validated knowledge. Policy effect stays none."""
        memory = self.require(memory_id)
        if memory.status is not MemoryStatus.VALIDATED:
            raise PromotionError("approval requires a validated candidate")
        if memory.untrusted_instruction:
            raise PromotionError("untrusted instructions cannot be approved")
        approved_knowledge = memory.category is not MemoryCategory.SIMULATION
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE organism_memories
                SET status = ?, approved_knowledge = ?, policy_effect = 'none', updated_at = ?
                WHERE memory_id = ?
                """,
                (
                    MemoryStatus.APPROVED.value,
                    1 if approved_knowledge else 0,
                    _now().isoformat(),
                    memory_id,
                ),
            )
            _event(
                connection,
                memory_id,
                "approved",
                {
                    "approver": approver,
                    "approved_knowledge": approved_knowledge,
                    "policy_effect": "none",
                },
            )
        return self.require(memory_id)

    def correct(
        self,
        memory_id: str,
        content: str,
        reason: str,
        *,
        owner_id: str,
    ) -> OrganismMemory:
        """Append a correction. The original content row is not rewritten."""
        original = self.require(memory_id)
        if original.status is MemoryStatus.DELETED:
            raise PromotionError("deleted memory cannot be corrected")
        if not content.strip():
            raise PromotionError("correction content must not be empty")
        correction = self._insert(
            category=MemoryCategory.CORRECTION,
            status=MemoryStatus.RECORDED,
            content=content,
            owner_id=owner_id,
            project_id=original.project_id,
            confidence=original.confidence,
            confidence_basis="operator",
            sensitivity=original.sensitivity,
            approved_knowledge=False,
            untrusted_instruction=looks_like_untrusted_instruction(content),
            source_evidence_ids=list(original.source_evidence_ids),
            source_memory_ids=[original.memory_id],
            parent_memory_id=original.memory_id,
            valid_until=None,
            event_type="correction",
            event_detail={"reason": reason, "corrects": original.memory_id},
        )
        contradictable = {
            MemoryStatus.APPROVED,
            MemoryStatus.VALIDATED,
            MemoryStatus.RECORDED,
        }
        if original.status in contradictable:
            self._set_status(
                original.memory_id,
                MemoryStatus.CONTRADICTED,
                "contradicted",
                {"correction_id": correction.memory_id, "reason": reason},
            )
            self._link_contradiction(original.memory_id, correction.memory_id, reason)
        unchanged = self.require(original.memory_id)
        if unchanged.content_sha256 != original.content_sha256:
            raise PromotionError("correction rewrote original content")
        return correction

    def contradict(self, memory_id: str, other_memory_id: str, reason: str) -> None:
        """Mark two memories as contradicting each other."""
        left = self.require(memory_id)
        right = self.require(other_memory_id)
        for memory in (left, right):
            if memory.status is not MemoryStatus.DELETED:
                self._set_status(
                    memory.memory_id,
                    MemoryStatus.CONTRADICTED,
                    "contradicted",
                    {"reason": reason},
                )
        self._link_contradiction(memory_id, other_memory_id, reason)

    def delete(self, memory_id: str, reason: str) -> OrganismMemory:
        """Remove memory text from retrieval and reject dependent drafts."""
        memory = self.require(memory_id)
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE organism_memories
                SET status = ?, content = ?, updated_at = ?
                WHERE memory_id = ?
                """,
                (MemoryStatus.DELETED.value, self._seal(""), _now().isoformat(), memory_id),
            )
            _event(connection, memory_id, "deleted", {"reason": reason})
            children = connection.execute(
                """
                SELECT memory_id, status FROM organism_memories
                WHERE parent_memory_id = ?
                """,
                (memory_id,),
            ).fetchall()
            for child in children:
                if str(child["status"]) in {
                    MemoryStatus.RECORDED.value,
                    MemoryStatus.CANDIDATE.value,
                    MemoryStatus.VALIDATED.value,
                }:
                    connection.execute(
                        """
                        UPDATE organism_memories
                        SET status = ?, updated_at = ?
                        WHERE memory_id = ?
                        """,
                        (
                            MemoryStatus.REJECTED.value,
                            _now().isoformat(),
                            str(child["memory_id"]),
                        ),
                    )
                    _event(
                        connection,
                        str(child["memory_id"]),
                        "rejected",
                        {"reason": "source memory deleted"},
                    )
        deleted = self.require(memory_id)
        if deleted.content_sha256 != memory.content_sha256:
            raise PromotionError("deletion changed the content hash")
        return deleted

    def search(
        self,
        query: str,
        *,
        owner_id: str | None = None,
        project_id: str | None = None,
        include_global: bool = False,
        category: MemoryCategory | None = None,
        min_confidence: float = 0.0,
        include_contradicted: bool = False,
        include_stale: bool = False,
        include_simulation: bool = False,
        include_untrusted_instructions: bool = False,
        limit: int = 10,
    ) -> list[RetrievalHit]:
        """Rank retained memories with BM25, confidence, and recency."""
        memories = self._all()
        eligible: list[OrganismMemory] = []
        for memory in memories:
            if memory.status is MemoryStatus.DELETED or memory.content is None:
                continue
            if owner_id is not None and memory.owner_id != owner_id:
                continue
            if project_id is not None:
                if memory.project_id != project_id and not (
                    include_global and memory.project_id is None
                ):
                    continue
            if category is not None and memory.category is not category:
                continue
            if memory.confidence < min_confidence:
                continue
            if memory.untrusted_instruction and not include_untrusted_instructions:
                continue
            if memory.category is MemoryCategory.SIMULATION and not include_simulation:
                if category is not MemoryCategory.SIMULATION:
                    continue
            visible = memory.status in {MemoryStatus.RECORDED, MemoryStatus.APPROVED}
            if memory.status is MemoryStatus.CONTRADICTED and include_contradicted:
                visible = True
            if not visible:
                continue
            effective = memory.effective_status
            if effective == "stale" and not include_stale:
                continue
            eligible.append(memory)
        scores = bm25_scores(
            query,
            [(memory.memory_id, memory.content or "") for memory in eligible],
        )
        now = _now()
        ranked: list[RetrievalHit] = []
        for memory in eligible:
            age_days = max(0.0, (now - memory.created_at).total_seconds() / 86400.0)
            recency = 1.0 / (1.0 + age_days)
            lexical = scores.get(memory.memory_id, 0.0)
            if query.strip() and lexical <= 0.0:
                continue
            score = (lexical if query.strip() else recency) * (0.5 + 0.5 * memory.confidence) * (
                recency if query.strip() else 1.0
            )
            ranked.append(
                RetrievalHit(
                    memory=memory,
                    score=score,
                    effective_status=memory.effective_status,
                )
            )
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return ranked[:limit]

    def _seal(self, plaintext: str) -> str:
        return seal_field(self.cipher, plaintext)

    def require(self, memory_id: str) -> OrganismMemory:
        """Return a memory or raise when it is absent."""
        memory = self.get(memory_id)
        if memory is None:
            raise KeyError(f"unknown memory: {memory_id}")
        return memory

    def get(self, memory_id: str) -> OrganismMemory | None:
        """Return one memory. Deleted memories omit content."""
        self.migrate()
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM organism_memories WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
        if row is None:
            return None
        return _memory_from_row(row, self.cipher)

    def export_owner(self, owner_id: str) -> dict[str, Any]:
        """Export retained memories and evidence citations for an owner."""
        retained = [
            memory.model_dump(mode="json")
            for memory in self._all()
            if memory.owner_id == owner_id and memory.status is not MemoryStatus.DELETED
        ]
        deleted = [
            {"memory_id": memory.memory_id, "content_sha256": memory.content_sha256}
            for memory in self._all()
            if memory.owner_id == owner_id and memory.status is MemoryStatus.DELETED
        ]
        return {
            "owner_id": owner_id,
            "memories": retained,
            "deleted": deleted,
            "policy_effect": "none",
        }

    def capability_status(self) -> str:
        """Return available or degraded from evidence integrity."""
        try:
            if not self.evidence.verify_chain():
                return "degraded"
        except DataKeyError:
            return "degraded"
        return "available"

    def status(self) -> dict[str, Any]:
        """Return organism and evidence capability status."""
        try:
            memories = self._all()
        except DataKeyError as exc:
            return {
                "capability": "memory_organism",
                "status": "degraded",
                "durable": True,
                "backend": "sqlite",
                "schema_version": SCHEMA_VERSION,
                "local_first": True,
                "network": "none",
                "encrypted_at_rest": True,
                "cryptographic_immutability": False,
                "reason": str(exc),
                "db_path": str(self.db_path),
                "policy_effect": "none",
            }
        counts: dict[str, int] = {category.value: 0 for category in MemoryCategory}
        for memory in memories:
            if memory.status is not MemoryStatus.DELETED:
                counts[memory.category.value] += 1
        evidence = self.evidence.status()
        return {
            "capability": "memory_organism",
            "status": "available" if evidence["status"] == "available" else "degraded",
            "durable": True,
            "backend": "sqlite",
            "schema_version": SCHEMA_VERSION,
            "local_first": True,
            "network": "none",
            "encrypted_at_rest": self.cipher is not None,
            "policy_effect": "none",
            "memory_count": sum(counts.values()),
            "categories": counts,
            "evidence": evidence,
            "db_path": str(self.db_path),
            "continuity_checkpoints_bound": self.continuity_bound,
            "limitations": [
                "BM25 scores are uncalibrated retrieval weights.",
                "Approval cannot modify security policy or persistent instructions.",
                "Simulation memory cannot be promoted into factual knowledge.",
                "Evidence headers are tamper-evident, not cryptographically immutable.",
                "Continuity checkpoint evidence cites digests only, and only after binding.",
            ],
        }

    def _insert(
        self,
        *,
        category: MemoryCategory,
        status: MemoryStatus,
        content: str,
        owner_id: str,
        project_id: str | None,
        confidence: float,
        confidence_basis: str,
        sensitivity: str,
        approved_knowledge: bool,
        untrusted_instruction: bool,
        source_evidence_ids: list[str],
        source_memory_ids: list[str],
        parent_memory_id: str | None,
        valid_until: datetime | None,
        event_type: str,
        event_detail: dict[str, Any],
    ) -> OrganismMemory:
        confidence = _bounded(confidence)
        now = _now()
        memory_id = str(uuid4())
        digest = sha256_text(content)
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO organism_memories (
                    memory_id, category, status, content, content_sha256, owner_id,
                    project_id, confidence, confidence_basis, sensitivity,
                    approved_knowledge, policy_effect, untrusted_instruction,
                    source_evidence_json, source_memory_json, parent_memory_id,
                    valid_until, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'none', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    category.value,
                    status.value,
                    self._seal(content),
                    digest,
                    owner_id,
                    project_id,
                    confidence,
                    confidence_basis,
                    sensitivity,
                    1 if approved_knowledge else 0,
                    1 if untrusted_instruction else 0,
                    json.dumps(source_evidence_ids),
                    json.dumps(source_memory_ids),
                    parent_memory_id,
                    None if valid_until is None else valid_until.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            _event(connection, memory_id, event_type, event_detail)
        return self.require(memory_id)

    def _set_status(
        self,
        memory_id: str,
        status: MemoryStatus,
        event_type: str,
        detail: dict[str, Any],
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE organism_memories
                SET status = ?, updated_at = ?
                WHERE memory_id = ?
                """,
                (status.value, _now().isoformat(), memory_id),
            )
            _event(connection, memory_id, event_type, detail)

    def _link_contradiction(self, memory_id: str, other_memory_id: str, reason: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO organism_contradictions (
                    contradiction_id, memory_id, other_memory_id, reason, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid4()), memory_id, other_memory_id, reason, _now().isoformat()),
            )

    def _all(self) -> list[OrganismMemory]:
        self.migrate()
        with self._read() as connection:
            rows = connection.execute(
                "SELECT * FROM organism_memories ORDER BY created_at ASC"
            ).fetchall()
        return [_memory_from_row(row, self.cipher) for row in rows]

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def _now() -> datetime:
    return datetime.now(UTC)


def _bounded(confidence: float) -> float:
    if confidence < 0.0 or confidence > 1.0:
        raise PromotionError("confidence must be between 0 and 1")
    return confidence


def _organism_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT MAX(version) AS version FROM organism_schema_migrations"
    ).fetchone()
    if row is None or row["version"] is None:
        return 0
    return int(row["version"])


def _execute_sql_script(connection: sqlite3.Connection, script: str) -> None:
    for statement in script.split(";"):
        sql = statement.strip()
        if sql:
            connection.execute(sql)


def _event(
    connection: sqlite3.Connection,
    memory_id: str,
    event_type: str,
    detail: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO organism_events (event_id, memory_id, event_type, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            memory_id,
            event_type,
            canonical_json(detail),
            _now().isoformat(),
        ),
    )


def _json_list(text: str) -> list[str]:
    loaded: object = json.loads(text)
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _memory_from_row(row: sqlite3.Row, cipher: FieldCipher | None) -> OrganismMemory:
    status = MemoryStatus(str(row["status"]))
    content = open_field(cipher, str(row["content"]))
    valid = row["valid_until"]
    return OrganismMemory(
        memory_id=str(row["memory_id"]),
        category=MemoryCategory(str(row["category"])),
        status=status,
        content=None if status is MemoryStatus.DELETED else content,
        content_sha256=str(row["content_sha256"]),
        owner_id=str(row["owner_id"]),
        project_id=None if row["project_id"] is None else str(row["project_id"]),
        confidence=float(row["confidence"]),
        confidence_basis=str(row["confidence_basis"]),
        sensitivity=str(row["sensitivity"]),
        approved_knowledge=bool(row["approved_knowledge"]),
        policy_effect=str(row["policy_effect"]),
        untrusted_instruction=bool(row["untrusted_instruction"]),
        source_evidence_ids=_json_list(str(row["source_evidence_json"])),
        source_memory_ids=_json_list(str(row["source_memory_json"])),
        parent_memory_id=(
            None if row["parent_memory_id"] is None else str(row["parent_memory_id"])
        ),
        valid_until=None if valid is None else datetime.fromisoformat(str(valid)),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )
