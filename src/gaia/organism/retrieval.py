"""Local BM25 ranking for organism memories.

Scores are relative retrieval weights. They are not calibrated probabilities.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")
_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens."""
    return _TOKEN.findall(text.lower())


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
