"""Append-only local evidence ledger.

Header rows are insert-only. Bodies live in a separate table so an expired
purge can remove text without rewriting the hash chain. This detects corruption
and naive edits. It is not cryptographic immutability against a privileged
local writer.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from gaia.evidence.codec import canonical_json, sha256_text
from gaia.security.field_cipher import (
    DataKeyError,
    FieldCipher,
    open_field,
    seal_field,
    seal_if_plain,
)

SCHEMA_VERSION = 1
GENESIS = "genesis"

_SOURCES = frozenset({"user", "operator", "tool", "model", "document", "system"})
_CLASSIFICATIONS = frozenset({"public", "internal", "sensitive", "restricted"})

LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS evidence_schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_records (
    evidence_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    origin TEXT NOT NULL,
    created_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    producer TEXT NOT NULL,
    execution_id TEXT,
    mime_type TEXT NOT NULL,
    classification TEXT NOT NULL,
    license TEXT,
    retention_policy TEXT NOT NULL,
    retain_until TEXT,
    parent_evidence_id TEXT,
    relationship TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    record_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_bodies (
    evidence_id TEXT PRIMARY KEY,
    content_text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_purges (
    evidence_id TEXT PRIMARY KEY,
    content_sha256 TEXT NOT NULL,
    reason TEXT NOT NULL,
    purged_at TEXT NOT NULL
);
"""

DROP_EVIDENCE_V1 = """
DROP TABLE IF EXISTS evidence_purges;
DROP TABLE IF EXISTS evidence_bodies;
DROP TABLE IF EXISTS evidence_records;
"""


class EvidenceError(ValueError):
    """Raised when an evidence operation violates the ledger rules."""


class EvidenceRecord(BaseModel):
    """One evidence header plus its body when the body has not been purged."""

    evidence_id: str
    source: str
    origin: str
    created_at: datetime
    content_sha256: str
    content_text: str | None = None
    purged: bool = False
    producer: str
    execution_id: str | None = None
    mime_type: str
    classification: str
    license: str | None = None
    retention_policy: str
    retain_until: datetime | None = None
    parent_evidence_id: str | None = None
    relationship: str
    previous_hash: str
    record_sha256: str


class EvidenceLedger:
    """Local SQLite evidence ledger."""

    def __init__(self, db_path: Path | str, *, cipher: FieldCipher | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cipher = cipher
        self.migrate()
        if cipher is not None:
            self.reseal_plaintext()

    def migrate(self) -> int:
        """Apply the evidence schema and return its version."""
        with self._transaction() as connection:
            _execute_sql_script(connection, LEDGER_SQL)
            row = connection.execute(
                "SELECT MAX(version) AS version FROM evidence_schema_migrations"
            ).fetchone()
            current = 0 if row is None or row["version"] is None else int(row["version"])
            if current < 1:
                connection.execute(
                    """
                    INSERT INTO evidence_schema_migrations (version, name, applied_at)
                    VALUES (1, 'evidence_initial', ?)
                    """,
                    (_now().isoformat(),),
                )
                current = 1
            if current > SCHEMA_VERSION:
                raise EvidenceError(
                    f"evidence schema {current} is newer than this build ({SCHEMA_VERSION})"
                )
            return current

    def reseal_plaintext(self) -> int:
        """Encrypt plaintext bodies in place. Header digests stay hashes of plaintext."""
        if self.cipher is None:
            return 0
        changed = 0
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT evidence_id, content_text FROM evidence_bodies"
            ).fetchall()
            for row in rows:
                sealed = seal_if_plain(self.cipher, str(row["content_text"]))
                if sealed is None:
                    continue
                connection.execute(
                    "UPDATE evidence_bodies SET content_text = ? WHERE evidence_id = ?",
                    (sealed, str(row["evidence_id"])),
                )
                changed += 1
        return changed

    def rollback_schema(self, target: int, *, force: bool = False) -> int:
        """Drop evidence tables back to version 0 when forced.

        Version 0 removes headers, bodies, and purge receipts. The migration
        table remains with no applied version. The next open migrates to
        version 1 again. Organism and continuity tables in the same file are
        left in place.
        """
        if target < 0 or target > SCHEMA_VERSION:
            raise ValueError(f"unsupported evidence schema target: {target}")
        self.migrate()
        with self._transaction() as connection:
            current = _schema_version(connection)
            if target > current:
                raise ValueError("schema rollback target is newer than the applied version")
            if target == current:
                return current
            count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM evidence_records"
            ).fetchone()
            record_count = 0 if count_row is None else int(count_row["count"])
            if record_count and not force:
                raise EvidenceError(
                    "schema rollback would drop evidence history; pass force=True"
                )
            if target == 0 and current >= 1:
                _execute_sql_script(connection, DROP_EVIDENCE_V1)
                connection.execute("DELETE FROM evidence_schema_migrations WHERE version >= 1")
            return _schema_version(connection)

    def append(
        self,
        *,
        source: str,
        origin: str,
        content: str,
        producer: str,
        mime_type: str = "text/plain",
        classification: str = "internal",
        execution_id: str | None = None,
        license_name: str | None = None,
        retention_policy: str = "keep",
        retain_until: datetime | None = None,
        parent_evidence_id: str | None = None,
        relationship: str = "raw",
    ) -> EvidenceRecord:
        """Append one evidence record. Content is stored separately from its header."""
        if source not in _SOURCES:
            raise EvidenceError(f"unsupported evidence source: {source}")
        if classification not in _CLASSIFICATIONS:
            raise EvidenceError(f"unsupported classification: {classification}")
        if not content.strip():
            raise EvidenceError("evidence content must not be empty")
        if retention_policy not in {"keep", "until"}:
            raise EvidenceError("retention_policy must be keep or until")
        if retention_policy == "until" and retain_until is None:
            raise EvidenceError("retention_policy until requires retain_until")
        content_hash = sha256_text(content)
        with self._transaction() as connection:
            previous = _latest_hash(connection)
            header = {
                "classification": classification,
                "content_sha256": content_hash,
                "execution_id": execution_id,
                "license": license_name,
                "mime_type": mime_type,
                "origin": origin,
                "parent_evidence_id": parent_evidence_id,
                "previous_hash": previous,
                "producer": producer,
                "relationship": relationship,
                "retain_until": None if retain_until is None else retain_until.isoformat(),
                "retention_policy": retention_policy,
                "source": source,
            }
            evidence_id = str(uuid4())
            created_at = _now()
            header["created_at"] = created_at.isoformat()
            header["evidence_id"] = evidence_id
            record_hash = sha256_text(canonical_json(header))
            connection.execute(
                """
                INSERT INTO evidence_records (
                    evidence_id, source, origin, created_at, content_sha256, producer,
                    execution_id, mime_type, classification, license, retention_policy,
                    retain_until, parent_evidence_id, relationship, previous_hash, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    source,
                    origin,
                    created_at.isoformat(),
                    content_hash,
                    producer,
                    execution_id,
                    mime_type,
                    classification,
                    license_name,
                    retention_policy,
                    None if retain_until is None else retain_until.isoformat(),
                    parent_evidence_id,
                    relationship,
                    previous,
                    record_hash,
                ),
            )
            connection.execute(
                "INSERT INTO evidence_bodies (evidence_id, content_text) VALUES (?, ?)",
                (evidence_id, seal_field(self.cipher, content)),
            )
        loaded = self.get(evidence_id)
        if loaded is None:
            raise EvidenceError("evidence append did not persist")
        return loaded

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        """Return one evidence record. Purged records omit the body."""
        self.migrate()
        with self._read() as connection:
            return _load(connection, evidence_id, self.cipher)

    def list_records(self) -> list[EvidenceRecord]:
        """Return evidence headers in chain order."""
        self.migrate()
        with self._read() as connection:
            rows = connection.execute(
                "SELECT evidence_id FROM evidence_records ORDER BY created_at ASC"
            ).fetchall()
            loaded = [
                _load(connection, str(row["evidence_id"]), self.cipher) for row in rows
            ]
        return [record for record in loaded if record is not None]

    def verify(self, evidence_id: str) -> bool:
        """Return whether one record matches its stored digest and body hash."""
        self.migrate()
        with self._read() as connection:
            return _record_ok(connection, evidence_id, self.cipher)

    def verify_chain(self) -> bool:
        """Return whether every header links to the previous record digest."""
        self.migrate()
        with self._read() as connection:
            return _chain_ok(connection, self.cipher)

    def purge_expired(self, *, now: datetime | None = None) -> list[str]:
        """Remove bodies whose retention instant has passed.

        Header digests and purge receipts remain so the chain can still be checked.
        """
        moment = now or _now()
        purged: list[str] = []
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT evidence_id, content_sha256, retain_until
                FROM evidence_records
                WHERE retention_policy = 'until' AND retain_until IS NOT NULL
                """
            ).fetchall()
            for row in rows:
                retain_until = datetime.fromisoformat(str(row["retain_until"]))
                if retain_until > moment:
                    continue
                evidence_id = str(row["evidence_id"])
                existing = connection.execute(
                    "SELECT evidence_id FROM evidence_purges WHERE evidence_id = ?",
                    (evidence_id,),
                ).fetchone()
                if existing is not None:
                    continue
                connection.execute(
                    "DELETE FROM evidence_bodies WHERE evidence_id = ?",
                    (evidence_id,),
                )
                connection.execute(
                    """
                    INSERT INTO evidence_purges (
                        evidence_id, content_sha256, reason, purged_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        str(row["content_sha256"]),
                        "retention instant passed",
                        moment.isoformat(),
                    ),
                )
                purged.append(evidence_id)
        return purged

    def status(self) -> dict[str, Any]:
        """Return ledger capability status."""
        encrypted = self.cipher is not None
        try:
            records = self.list_records()
            integrity_ok = self.verify_chain()
        except DataKeyError as exc:
            return {
                "capability": "evidence_ledger",
                "status": "degraded",
                "durable": True,
                "backend": "sqlite",
                "schema_version": SCHEMA_VERSION,
                "local_first": True,
                "network": "none",
                "encrypted_at_rest": True,
                "cryptographic_immutability": False,
                "reason": str(exc),
                "integrity": "degraded",
                "db_path": str(self.db_path),
            }
        return {
            "capability": "evidence_ledger",
            "status": "available" if integrity_ok else "degraded",
            "durable": True,
            "backend": "sqlite",
            "schema_version": SCHEMA_VERSION,
            "local_first": True,
            "network": "none",
            "encrypted_at_rest": encrypted,
            "cryptographic_immutability": False,
            "record_count": len(records),
            "purged_count": sum(1 for record in records if record.purged),
            "integrity": "verified" if integrity_ok else "degraded",
            "db_path": str(self.db_path),
        }

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
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
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


def _schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT MAX(version) AS version FROM evidence_schema_migrations"
    ).fetchone()
    if row is None or row["version"] is None:
        return 0
    return int(row["version"])


def _execute_sql_script(connection: sqlite3.Connection, script: str) -> None:
    for statement in script.split(";"):
        sql = statement.strip()
        if sql:
            connection.execute(sql)


def _now() -> datetime:
    return datetime.now(UTC)


def _latest_hash(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        """
        SELECT record_sha256 FROM evidence_records
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return GENESIS
    return str(row["record_sha256"])


def _load(
    connection: sqlite3.Connection,
    evidence_id: str,
    cipher: FieldCipher | None,
) -> EvidenceRecord | None:
    row = connection.execute(
        "SELECT * FROM evidence_records WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    if row is None:
        return None
    purge = connection.execute(
        "SELECT evidence_id FROM evidence_purges WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    body = connection.execute(
        "SELECT content_text FROM evidence_bodies WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    retain = row["retain_until"]
    return EvidenceRecord(
        evidence_id=str(row["evidence_id"]),
        source=str(row["source"]),
        origin=str(row["origin"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        content_sha256=str(row["content_sha256"]),
        content_text=None if body is None else open_field(cipher, str(body["content_text"])),
        purged=purge is not None,
        producer=str(row["producer"]),
        execution_id=None if row["execution_id"] is None else str(row["execution_id"]),
        mime_type=str(row["mime_type"]),
        classification=str(row["classification"]),
        license=None if row["license"] is None else str(row["license"]),
        retention_policy=str(row["retention_policy"]),
        retain_until=None if retain is None else datetime.fromisoformat(str(retain)),
        parent_evidence_id=(
            None if row["parent_evidence_id"] is None else str(row["parent_evidence_id"])
        ),
        relationship=str(row["relationship"]),
        previous_hash=str(row["previous_hash"]),
        record_sha256=str(row["record_sha256"]),
    )


def _header_hash(row: sqlite3.Row) -> str:
    header = {
        "classification": str(row["classification"]),
        "content_sha256": str(row["content_sha256"]),
        "created_at": str(row["created_at"]),
        "evidence_id": str(row["evidence_id"]),
        "execution_id": None if row["execution_id"] is None else str(row["execution_id"]),
        "license": None if row["license"] is None else str(row["license"]),
        "mime_type": str(row["mime_type"]),
        "origin": str(row["origin"]),
        "parent_evidence_id": (
            None if row["parent_evidence_id"] is None else str(row["parent_evidence_id"])
        ),
        "previous_hash": str(row["previous_hash"]),
        "producer": str(row["producer"]),
        "relationship": str(row["relationship"]),
        "retain_until": None if row["retain_until"] is None else str(row["retain_until"]),
        "retention_policy": str(row["retention_policy"]),
        "source": str(row["source"]),
    }
    return sha256_text(canonical_json(header))


def _record_ok(
    connection: sqlite3.Connection,
    evidence_id: str,
    cipher: FieldCipher | None,
) -> bool:
    row = connection.execute(
        "SELECT * FROM evidence_records WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    if row is None or _header_hash(row) != str(row["record_sha256"]):
        return False
    body = connection.execute(
        "SELECT content_text FROM evidence_bodies WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    purge = connection.execute(
        "SELECT content_sha256 FROM evidence_purges WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    if body is not None:
        opened = open_field(cipher, str(body["content_text"]))
        return sha256_text(opened) == str(row["content_sha256"])
    return purge is not None and str(purge["content_sha256"]) == str(row["content_sha256"])


def _chain_ok(connection: sqlite3.Connection, cipher: FieldCipher | None) -> bool:
    rows = connection.execute(
        "SELECT * FROM evidence_records ORDER BY created_at ASC"
    ).fetchall()
    expected = GENESIS
    for row in rows:
        if str(row["previous_hash"]) != expected or not _record_ok(
            connection, str(row["evidence_id"]), cipher
        ):
            return False
        expected = str(row["record_sha256"])
    return True
