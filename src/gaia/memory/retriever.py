"""Semantic memory retrieval over the in-process vector index.

Returned scores are cosine similarity on a deterministic hash embedding.
They are uncalibrated.
"""

from __future__ import annotations

from dataclasses import dataclass

from .indexer import simple_embedding
from .vector_store import VectorSearchResult, VectorStore


@dataclass(slots=True)
class MemoryRetriever:
    vector_store: VectorStore

    def retrieve(self, query: str, limit: int = 5) -> list[VectorSearchResult]:
        """Search the local vector index. Scores are uncalibrated cosine values."""
        return self.vector_store.search(simple_embedding(query), limit=limit)
