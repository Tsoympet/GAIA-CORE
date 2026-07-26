"""Symbolic memory graph for facts, relationships, and provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SymbolicFact:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    fact_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class SymbolicMemory:
    facts: dict[str, SymbolicFact] = field(default_factory=dict)

    def add(self, fact: SymbolicFact) -> SymbolicFact:
        self.facts[fact.fact_id] = fact
        return fact

    def query(
        self,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> list[SymbolicFact]:
        return [
            fact
            for fact in self.facts.values()
            if (subject is None or fact.subject == subject)
            and (predicate is None or fact.predicate == predicate)
        ]
