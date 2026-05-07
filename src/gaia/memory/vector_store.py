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
    def search(self, embedding: list[float], limit: int = 5) -> list[VectorSearchResult]: ...


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    denominator = sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b))
    return 0.0 if denominator == 0 else sum(x * y for x, y in zip(a, b, strict=True)) / denominator


@dataclass(slots=True)
class InMemoryVectorStore(VectorStore):
    documents: dict[str, VectorDocument] = field(default_factory=dict)

    def upsert(self, documents: list[VectorDocument]) -> None:
        for document in documents:
            self.documents[document.document_id] = document

    def search(self, embedding: list[float], limit: int = 5) -> list[VectorSearchResult]:
        results = [VectorSearchResult(doc, cosine(embedding, doc.embedding)) for doc in self.documents.values()]
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]
