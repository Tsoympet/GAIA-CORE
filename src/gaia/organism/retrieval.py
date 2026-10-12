"""Local hybrid ranking for organism memories.

The ranker combines BM25, character n-gram cosine, and light metadata overlap.
Scores are relative retrieval weights. They are not calibrated probabilities,
and they are not neural embeddings.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

_TOKEN = re.compile(r"[a-z0-9]+")
_K1 = 1.5
_B = 0.75
_NGRAM_SIZE = 3
_NGRAM_WEIGHT = 2.5
_NGRAM_MIN = 0.32
_METADATA_WEIGHT = 0.4


class RetrievalMode(StrEnum):
    """Operator-selectable local ranker."""

    BM25 = "bm25"
    HYBRID = "hybrid"


class ScoreComponents(BaseModel):
    """Uncalibrated parts of one retrieval score."""

    lexical: float
    ngram: float = 0.0
    metadata: float = 0.0
    recency: float
    confidence: float
    ranker: RetrievalMode = RetrievalMode.HYBRID


@dataclass(frozen=True, slots=True)
class RankedDocument:
    """One memory surface used by the local ranker."""

    document_id: str
    text: str
    confidence: float
    created_at: datetime
    category: str = ""
    project_id: str | None = None
    owner_id: str = ""


def tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens."""
    return _TOKEN.findall(text.lower())


def char_ngrams(text: str, size: int = _NGRAM_SIZE) -> Counter[str]:
    """Return character n-grams for morphological overlap.

    Tokens are folded to ``[a-z0-9]``. This is a lexical similarity feature,
    not a learned embedding.
    """
    grams: Counter[str] = Counter()
    for token in tokenize(text):
        padded = f"#{token}#"
        if len(padded) <= size:
            grams[padded] += 1
            continue
        for index in range(len(padded) - size + 1):
            grams[padded[index : index + size]] += 1
    return grams


def ngram_cosine(query: str, document: str) -> float:
    """Return cosine similarity of character n-gram counts."""
    left = char_ngrams(query)
    right = char_ngrams(document)
    if not left or not right:
        return 0.0
    keys = set(left) | set(right)
    numerator = sum(left[key] * right[key] for key in keys)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def metadata_overlap(
    query: str,
    *,
    category: str = "",
    project_id: str | None = None,
    owner_id: str = "",
) -> float:
    """Return 1.0 when a query token matches category, project, or owner tokens."""
    terms = set(tokenize(query))
    if not terms:
        return 0.0
    haystack = set(tokenize(category))
    if project_id is not None:
        haystack.update(tokenize(project_id))
    haystack.update(tokenize(owner_id))
    return 1.0 if terms & haystack else 0.0


def bm25_scores(query: str, documents: list[tuple[str, str]]) -> dict[str, float]:
    """Return a BM25 score for each document id."""
    query_terms = tokenize(query)
    tokenized = [(doc_id, tokenize(text)) for doc_id, text in documents]
    if not query_terms or not tokenized:
        return {doc_id: 0.0 for doc_id, _ in documents}
    doc_count = len(tokenized)
    lengths = [len(tokens) for _, tokens in tokenized]
    average = sum(lengths) / doc_count if doc_count else 0.0
    document_frequency: Counter[str] = Counter()
    for _, tokens in tokenized:
        document_frequency.update(set(tokens))
    scores: dict[str, float] = {}
    for (doc_id, tokens), length in zip(tokenized, lengths, strict=True):
        counts = Counter(tokens)
        score = 0.0
        for term in query_terms:
            if term not in counts:
                continue
            df = document_frequency[term]
            idf = math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5))
            frequency = counts[term]
            denominator = frequency + _K1 * (
                1.0 - _B + _B * (length / average if average else 0.0)
            )
            score += idf * (frequency * (_K1 + 1.0)) / denominator
        scores[doc_id] = score
    return scores


def recency_weight(created_at: datetime, now: datetime) -> float:
    """Decay by age in days. The weight is not a probability."""
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return 1.0 / (1.0 + age_days)


def rank_documents(
    query: str,
    documents: list[RankedDocument],
    *,
    now: datetime,
    mode: RetrievalMode = RetrievalMode.HYBRID,
) -> dict[str, tuple[float, ScoreComponents]]:
    """Rank documents with BM25 or hybrid local features.

    An empty query ranks by recency only. A non-empty BM25 query keeps the
    historical rule that a document with no lexical overlap is omitted.
    Hybrid keeps documents with lexical or n-gram overlap.
    """
    stripped = query.strip()
    lexical_scores = bm25_scores(
        query,
        [(document.document_id, document.text) for document in documents],
    )
    ranked: dict[str, tuple[float, ScoreComponents]] = {}
    for document in documents:
        lexical = lexical_scores.get(document.document_id, 0.0)
        ngram = ngram_cosine(query, document.text) if stripped else 0.0
        metadata = (
            metadata_overlap(
                query,
                category=document.category,
                project_id=document.project_id,
                owner_id=document.owner_id,
            )
            if stripped
            else 0.0
        )
        recency = recency_weight(document.created_at, now)
        confidence = 0.5 + 0.5 * document.confidence
        if not stripped:
            score = recency
            components = ScoreComponents(
                lexical=0.0,
                recency=recency,
                confidence=confidence,
                ranker=mode,
            )
            ranked[document.document_id] = (score, components)
            continue
        if mode is RetrievalMode.BM25:
            if lexical <= 0.0:
                continue
            raw = lexical
        else:
            if lexical <= 0.0 and ngram < _NGRAM_MIN:
                continue
            raw = lexical + _NGRAM_WEIGHT * ngram + _METADATA_WEIGHT * metadata
        score = raw * confidence * recency
        ranked[document.document_id] = (
            score,
            ScoreComponents(
                lexical=lexical,
                ngram=ngram,
                metadata=metadata,
                recency=recency,
                confidence=confidence,
                ranker=mode,
            ),
        )
    return ranked


def query_index_keys(query: str) -> tuple[set[str], set[str]]:
    """Return unique query tokens and n-grams for posting lookup."""
    return set(tokenize(query)), set(char_ngrams(query))
