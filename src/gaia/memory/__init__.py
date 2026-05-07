"""Memory foundation exports."""

from .indexer import MemoryIndexer, simple_embedding
from .manager import MemoryManager
from .policies import MemoryPolicy
from .retriever import MemoryRetriever
from .scoped import MemoryRecord, MemoryScope, ScopedMemory
from .symbolic import SymbolicFact, SymbolicMemory
from .vector_store import InMemoryVectorStore, VectorDocument, VectorSearchResult, VectorStore

__all__ = [
    "InMemoryVectorStore", "MemoryIndexer", "MemoryManager", "MemoryPolicy", "MemoryRecord",
    "MemoryRetriever", "MemoryScope", "ScopedMemory", "SymbolicFact", "SymbolicMemory",
    "VectorDocument", "VectorSearchResult", "VectorStore", "simple_embedding",
]
"""Persistent memory interfaces for semantic, episodic, task, and project memory."""

from gaia.memory.store import MemoryEvent, MemoryStore, create_memory_store

__all__ = ["MemoryEvent", "MemoryStore", "create_memory_store"]
