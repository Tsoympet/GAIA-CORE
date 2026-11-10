"""Durable local index for phase-4 scoped memory.

Records and their hashed n-gram vectors live in one SQLite file. Search still
uses uncalibrated cosine similarity over those stored vectors. No weights are
downloaded, and the scores are not probabilities or confidence.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from gaia.memory.scoped import MemoryRecord, MemoryScope
from gaia.memory.vector_store import VectorDocument, VectorSearchResult, VectorStore, cosine


class SQLiteVectorIndex(VectorStore):
    """Phase-4 records plus the hashed vectors used to rank them."""

    def __init__(self, db_path: Path | str = Path(".gaia/phase4.sqlite3")) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.documents: dict[str, VectorDocument] = {}
        self.records: dict[str, MemoryRecord] = {}
        self._closed = False
        self._initialize()
        self._load()

    def close(self) -> None:
        """Drop the in-process cache. The SQLite file remains the source of truth."""
        self.documents.clear()
        self.records.clear()
        self._closed = True

    def load_records(self) -> list[MemoryRecord]:
        """Return scoped records currently cached from the SQLite file."""
        self._require_open()
        return list(self.records.values())

    def save_record(self, record: MemoryRecord) -> None:
        """Insert or replace one scoped record. This does not write a vector."""
        self._require_open()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO phase4_records (
                    record_id, scope, owner_id, content, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    scope = excluded.scope,
                    owner_id = excluded.owner_id,
                    content = excluded.content,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at
                """,
                (
                    record.record_id,
                    record.scope.value,
                    record.owner_id,
                    record.content,
                    json.dumps(record.metadata, sort_keys=True),
                    record.created_at.isoformat(),
                ),
            )
        self.records[record.record_id] = record

    def upsert(self, documents: list[VectorDocument]) -> None:
        self._require_open()
        with self._connect() as connection:
            for document in documents:
                connection.execute(
                    """
                    INSERT INTO phase4_vectors (
                        document_id, text, embedding_json, metadata_json
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(document_id) DO UPDATE SET
                        text = excluded.text,
                        embedding_json = excluded.embedding_json,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        document.document_id,
                        document.text,
                        json.dumps(document.embedding),
                        json.dumps(document.metadata, sort_keys=True),
                    ),
                )
                self.documents[document.document_id] = document

    def search(
        self,
        embedding: list[float],
        limit: int = 5,
    ) -> list[VectorSearchResult]:
        """Rank stored vectors. Scores are uncalibrated cosine similarity."""
        self._require_open()
        results = [
            VectorSearchResult(document, cosine(embedding, document.embedding))
            for document in self.documents.values()
        ]
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

    def delete(self, document_ids: list[str]) -> int:
        """Remove vectors and the scoped records that share those ids."""
        self._require_open()
        removed = 0
        with self._connect() as connection:
            for document_id in document_ids:
                had_vector = document_id in self.documents
                connection.execute(
                    "DELETE FROM phase4_vectors WHERE document_id = ?",
                    (document_id,),
                )
                connection.execute(
                    "DELETE FROM phase4_records WHERE record_id = ?",
                    (document_id,),
                )
                self.documents.pop(document_id, None)
                self.records.pop(document_id, None)
                if had_vector:
                    removed += 1
        return removed

    def count(self) -> int:
        self._require_open()
        return len(self.documents)

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("phase-4 index is closed")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS phase4_records (
                    record_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS phase4_vectors (
                    document_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_phase4_records_owner
                ON phase4_records (owner_id, scope)
                """
            )

    def _load(self) -> None:
        with self._connect() as connection:
            record_rows = connection.execute(
                """
                SELECT record_id, scope, owner_id, content, metadata_json, created_at
                FROM phase4_records
                """
            ).fetchall()
            vector_rows = connection.execute(
                """
                SELECT document_id, text, embedding_json, metadata_json
                FROM phase4_vectors
                """
            ).fetchall()
        self.records = {str(row["record_id"]): _record_from_row(row) for row in record_rows}
        self.documents = {
            str(row["document_id"]): _document_from_row(row) for row in vector_rows
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _record_from_row(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        content=str(row["content"]),
        scope=MemoryScope(str(row["scope"])),
        owner_id=str(row["owner_id"]),
        metadata=_object_from_json(str(row["metadata_json"])),
        record_id=str(row["record_id"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _document_from_row(row: sqlite3.Row) -> VectorDocument:
    return VectorDocument(
        text=str(row["text"]),
        embedding=_embedding_from_json(str(row["embedding_json"])),
        metadata=_object_from_json(str(row["metadata_json"])),
        document_id=str(row["document_id"]),
    )


def _object_from_json(raw: str) -> dict[str, Any]:
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        return {}
    return {str(key): value for key, value in loaded.items()}


def _embedding_from_json(raw: str) -> list[float]:
    loaded = json.loads(raw)
    if not isinstance(loaded, list) or any(isinstance(item, bool) for item in loaded):
        raise ValueError("stored embedding is not a float vector")
    if not all(isinstance(item, int | float) for item in loaded):
        raise ValueError("stored embedding is not a float vector")
    return [float(item) for item in loaded]
