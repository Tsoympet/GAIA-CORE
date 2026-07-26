"""Vector store abstraction with an in-memory cosine implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from math import sqrt
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class VectorDocument:
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    document_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    document: VectorDocument
    score: float


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, documents: list[VectorDocument]) -> None: ...

    @abstractmethod
    def search(
        self,
        embedding: list[float],
        limit: int = 5,
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    def delete(self, document_ids: list[str]) -> int:
        """Delete documents by stable ID and return the number removed."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of indexed documents."""


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    denominator = sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b))
    if denominator == 0:
        return 0.0
    numerator = sum(x * y for x, y in zip(a, b, strict=True))
    return numerator / denominator


@dataclass(slots=True)
class InMemoryVectorStore(VectorStore):
    documents: dict[str, VectorDocument] = field(default_factory=dict)

    def upsert(self, documents: list[VectorDocument]) -> None:
        for document in documents:
            self.documents[document.document_id] = document

    def search(
        self,
        embedding: list[float],
        limit: int = 5,
    ) -> list[VectorSearchResult]:
        results = [
            VectorSearchResult(document, cosine(embedding, document.embedding))
            for document in self.documents.values()
        ]
        return sorted(
            results,
            key=lambda result: result.score,
            reverse=True,
        )[:limit]

    def delete(self, document_ids: list[str]) -> int:
        removed = 0
        for document_id in document_ids:
            if self.documents.pop(document_id, None) is not None:
                removed += 1
        return removed

    def count(self) -> int:
        return len(self.documents)
