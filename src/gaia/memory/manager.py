"""Facade for scoped, symbolic, and vector-backed memory."""

from __future__ import annotations

from dataclasses import dataclass, field

from .indexer import MemoryIndexer
from .policies import MemoryPolicy
from .retriever import MemoryRetriever
from .scoped import MemoryRecord, MemoryScope, ScopedMemory
from .symbolic import SymbolicFact, SymbolicMemory
from .vector_store import InMemoryVectorStore, VectorStore


@dataclass(slots=True)
class MemoryManager:
    vector_store: VectorStore = field(default_factory=InMemoryVectorStore)
    symbolic: SymbolicMemory = field(default_factory=SymbolicMemory)
    policy: MemoryPolicy = field(default_factory=MemoryPolicy)
    scoped: dict[MemoryScope, ScopedMemory] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for scope in MemoryScope:
            self.scoped.setdefault(scope, ScopedMemory(scope=scope))

    @property
    def indexer(self) -> MemoryIndexer:
        return MemoryIndexer(self.vector_store, self.policy)

    @property
    def retriever(self) -> MemoryRetriever:
        return MemoryRetriever(self.vector_store)

    def remember(self, content: str, scope: MemoryScope, owner_id: str, index: bool = True) -> MemoryRecord:
        record = self.scoped[scope].add(content, owner_id, {"index": index})
        if index:
            self.indexer.index([record])
        return record

    def add_fact(self, subject: str, predicate: str, object: str, confidence: float = 1.0) -> SymbolicFact:
        return self.symbolic.add(SymbolicFact(subject, predicate, object, confidence))
