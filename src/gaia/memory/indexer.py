"""Memory indexing helpers.

Scoped records are embedded with a deterministic hashed token and character
n-gram vector. Nothing is downloaded. Cosine scores from this index are
uncalibrated: they are not probabilities, confidence, or neural distances.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from math import sqrt

from gaia.memory.policies import MemoryPolicy
from gaia.memory.scoped import MemoryRecord
from gaia.memory.vector_store import VectorDocument, VectorStore

VECTOR_INDEX = "in-process-hashed-ngram"
SCORES_CALIBRATED = False
SCORE_NOTE = (
    "Cosine scores from the in-process hashed n-gram index are uncalibrated. "
    "They are not probabilities or confidence."
)
EMBEDDING_DIMENSIONS = 1024
# Ignore a lone hash collision. Related notes in the tests sit above this.
MIN_VECTOR_SCORE = 0.2

_TOKEN = re.compile(r"[a-z0-9]+")


def simple_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Hash tokens and character trigrams into a unit vector.

    The same text always produces the same vector. No model weights are used.
    """
    if dimensions < 1:
        raise ValueError("dimensions must be positive")
    vector = [0.0] * dimensions
    for feature in _features(text):
        digest = hashlib.blake2s(feature.encode("utf-8"), digest_size=4).digest()
        bucket = int.from_bytes(digest, "little") % dimensions
        # Positive weights keep a shared token from cancelling itself.
        vector[bucket] += 1.0
    norm = sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _features(text: str) -> list[str]:
    tokens = [token for token in _TOKEN.findall(text.lower()) if len(token) >= 2]
    features: list[str] = []
    for token in tokens:
        features.append(f"w:{token}")
        if len(token) < 3:
            continue
        for index in range(len(token) - 2):
            features.append(f"g:{token[index : index + 3]}")
    return features


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
                metadata={
                    **record.metadata,
                    "record_id": record.record_id,
                    "scope": record.scope.value,
                    "owner_id": record.owner_id,
                },
            )
            for record in records
            if self.policy.should_index(record)
        ]
        self.vector_store.upsert(documents)
        return len(documents)
