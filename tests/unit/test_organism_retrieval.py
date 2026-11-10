"""Hybrid organism retrieval: BM25, character n-grams, and derived index."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from gaia.organism.organism import MemoryCategory, MemoryOrganism, MemoryStatus
from gaia.organism.retrieval import (
    RankedDocument,
    RetrievalMode,
    bm25_scores,
    ngram_cosine,
    rank_documents,
)
from gaia.security.field_cipher import FieldCipher, is_sealed


def _evidence(organism: MemoryOrganism, content: str) -> str:
    record = organism.evidence.append(
        source="user",
        origin="note",
        content=content,
        producer="operator",
    )
    return record.evidence_id


def test_hybrid_ranks_a_morphological_variant_that_bm25_misses() -> None:
    now = datetime.now(UTC)
    documents = [
        RankedDocument(
            document_id="hull",
            text="hydrostatic stability of the hull compartment",
            confidence=1.0,
            created_at=now,
            category="episodic",
            project_id="hull",
        ),
        RankedDocument(
            document_id="gear",
            text="spur gear tooth bending stress",
            confidence=1.0,
            created_at=now,
            category="episodic",
            project_id="gearbox",
        ),
    ]
    lexical = bm25_scores("hydrostatics", [(item.document_id, item.text) for item in documents])
    assert lexical["hull"] == 0.0
    assert ngram_cosine("hydrostatics", documents[0].text) > 0.0

    hybrid = rank_documents("hydrostatics", documents, now=now, mode=RetrievalMode.HYBRID)
    bm25 = rank_documents("hydrostatics", documents, now=now, mode=RetrievalMode.BM25)
    assert "hull" in hybrid
    assert "hull" not in bm25
    assert hybrid["hull"][1].ngram > 0.0
    assert hybrid["hull"][1].ranker is RetrievalMode.HYBRID


def test_search_hybrid_finds_ngram_overlap_and_bm25_does_not(tmp_path: Path) -> None:
    organism = MemoryOrganism(tmp_path / "organism.sqlite3")
    hull = organism.record_episodic(
        _evidence(organism, "Hydrostatic stability of the hull compartment"),
        owner_id="local",
        project_id="hull",
    )
    organism.record_episodic(
        _evidence(organism, "Spur gear tooth bending was reviewed"),
        owner_id="local",
        project_id="gearbox",
    )

    hybrid = organism.search("hydrostatics", mode=RetrievalMode.HYBRID)
    bm25 = organism.search("hydrostatics", mode=RetrievalMode.BM25)
    assert [hit.memory.memory_id for hit in hybrid] == [hull.memory_id]
    assert bm25 == []
    assert hybrid[0].ranker is RetrievalMode.HYBRID
    assert hybrid[0].components is not None
    assert hybrid[0].components.ngram > 0.0
    assert hybrid[0].components.lexical == 0.0


def test_search_bm25_mode_keeps_exact_token_ranking(tmp_path: Path) -> None:
    organism = MemoryOrganism(tmp_path / "organism.sqlite3")
    hull = organism.record_episodic(
        _evidence(organism, "Hydrostatic stability of the hull compartment"),
        owner_id="local",
        project_id="hull",
    )
    organism.record_episodic(
        _evidence(organism, "Spur gear tooth bending was reviewed"),
        owner_id="local",
        project_id="gearbox",
    )
    hits = organism.search("hydrostatic", mode=RetrievalMode.BM25, project_id="hull")
    assert [hit.memory.memory_id for hit in hits] == [hull.memory_id]
    assert hits[0].ranker is RetrievalMode.BM25
    assert organism.search("hydrostatic", mode=RetrievalMode.BM25, project_id="gearbox") == []


def test_evidence_filter_and_time_window(tmp_path: Path) -> None:
    organism = MemoryOrganism(tmp_path / "organism.sqlite3")
    first_id = _evidence(organism, "Observed freeboard after the tide")
    second_id = _evidence(organism, "Observed freeboard before the storm")
    first = organism.record_episodic(first_id, owner_id="local")
    second = organism.record_episodic(second_id, owner_id="local")

    cited = organism.search("freeboard", evidence_id=first_id)
    assert [hit.memory.memory_id for hit in cited] == [first.memory_id]

    future = organism.search(
        "freeboard",
        since=datetime.now(UTC) + timedelta(days=1),
    )
    assert future == []
    past = organism.search(
        "freeboard",
        until=datetime.now(UTC) - timedelta(days=1),
    )
    assert past == []
    both = organism.search("freeboard")
    assert {hit.memory.memory_id for hit in both} == {first.memory_id, second.memory_id}


def test_deletion_removes_derived_retrieval_index(tmp_path: Path) -> None:
    path = tmp_path / "organism.sqlite3"
    organism = MemoryOrganism(path)
    memory = organism.record_episodic(
        _evidence(organism, "The pump curve was measured at 60 hertz"),
        owner_id="local",
    )
    stats = organism.retrieval_index_stats()
    assert stats["documents"] == 1
    assert stats["term_postings"] > 0
    assert stats["ngram_postings"] > 0
    assert stats["hashed_terms"] is True

    deleted = organism.delete(memory.memory_id, "remove pump note")
    assert deleted.status is MemoryStatus.DELETED
    assert organism.retrieval_index_stats()["documents"] == 0
    assert organism.search("hertz") == []
    with sqlite3.connect(path) as connection:
        postings = connection.execute(
            "SELECT COUNT(*) FROM organism_term_postings WHERE memory_id = ?",
            (memory.memory_id,),
        ).fetchone()
        ngrams = connection.execute(
            "SELECT COUNT(*) FROM organism_ngram_postings WHERE memory_id = ?",
            (memory.memory_id,),
        ).fetchone()
    assert postings is not None and int(postings[0]) == 0
    assert ngrams is not None and int(ngrams[0]) == 0


def test_schema_v3_backfills_index_and_rollback_drops_it(tmp_path: Path) -> None:
    path = tmp_path / "organism.sqlite3"
    organism = MemoryOrganism(path)
    memory = organism.record_episodic(
        _evidence(organism, "Observed freeboard before the schema change"),
        owner_id="local",
    )
    assert organism.migrate() == 3
    assert organism.rollback_schema(2, force=True) == 2
    with sqlite3.connect(path) as connection:
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "organism_retrieval_docs" not in tables
    assert organism.get(memory.memory_id) is not None

    upgraded = MemoryOrganism(path)
    assert upgraded.migrate() == 3
    assert upgraded.retrieval_index_stats()["documents"] == 1
    hits = upgraded.search("freeboard")
    assert hits[0].memory.memory_id == memory.memory_id


def test_encrypted_index_does_not_store_plaintext_terms(tmp_path: Path) -> None:
    path = tmp_path / "organism.sqlite3"
    secret = "token=super-secret observation"
    cipher = FieldCipher(AESGCM.generate_key(bit_length=256))
    organism = MemoryOrganism(path, cipher=cipher)
    memory = organism.record_episodic(_evidence(organism, secret), owner_id="local")
    raw = path.read_bytes()
    assert b"super-secret" not in raw
    assert organism.retrieval_index_stats()["documents"] == 1

    hits = organism.search("observation")
    assert hits[0].memory.memory_id == memory.memory_id
    with sqlite3.connect(path) as connection:
        content = connection.execute(
            "SELECT content FROM organism_memories WHERE memory_id = ?",
            (memory.memory_id,),
        ).fetchone()
        terms = connection.execute("SELECT term FROM organism_term_postings").fetchall()
    assert content is not None
    assert is_sealed(str(content[0]))
    assert all(b"super" not in str(row[0]).encode() for row in terms)
    assert all(len(str(row[0])) == 64 for row in terms)


def test_preference_stays_hidden_from_hybrid_default_search(tmp_path: Path) -> None:
    organism = MemoryOrganism(tmp_path / "organism.sqlite3")
    observation = organism.record_episodic(
        _evidence(organism, "The operator selected a chart style"),
        owner_id="local",
    )
    candidate = organism.propose_candidate(
        content="The operator keeps paper-charts",
        category=MemoryCategory.PREFERENCE,
        source_memory_ids=[observation.memory_id],
        owner_id="local",
    )
    organism.validate(candidate.memory_id, passed=True, notes="cited the request")
    organism.approve(candidate.memory_id, "operator")
    assert organism.search("paper-charts") == []
    included = organism.search("paper-charts", include_preference=True)
    assert included[0].memory.category is MemoryCategory.PREFERENCE
