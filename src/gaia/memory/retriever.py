"""Semantic memory retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from .indexer import simple_embedding
from .vector_store import VectorSearchResult, VectorStore


@dataclass(slots=True)
class MemoryRetriever:
    vector_store: VectorStore

    def retrieve(self, query: str, limit: int = 5) -> list[VectorSearchResult]:
        return self.vector_store.search(simple_embedding(query), limit=limit)
