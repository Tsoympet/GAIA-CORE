"""Memory indexing helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .policies import MemoryPolicy
from .scoped import MemoryRecord
from .vector_store import VectorDocument, VectorStore


def simple_embedding(text: str, dimensions: int = 32) -> list[float]:
    vector = [0.0] * dimensions
    for index, char in enumerate(text.encode("utf-8")):
        vector[index % dimensions] += float(char) / 255.0
    return vector


@dataclass(slots=True)
class MemoryIndexer:
    vector_store: VectorStore
    policy: MemoryPolicy

    def index(self, records: list[MemoryRecord]) -> int:
        documents = [
            VectorDocument(
                document_id=record.record_id,
                text=record.content,
                embedding=simple_embedding(record.content),
                metadata={**record.metadata, "record_id": record.record_id, "scope": record.scope.value},
            )
            for record in records
            if self.policy.should_index(record)
        ]
        self.vector_store.upsert(documents)
        return len(documents)
