# Changelog

## Unreleased

### Added

- Hybrid organism retrieval: default ranking combines BM25, character n-gram cosine, metadata overlap, confidence, and recency. `mode=bm25` keeps the earlier lexical-only ranker. Scores stay uncalibrated. This is not a neural embedding.
- Organism schema v3 stores a hashed term and n-gram index. Deletion removes those derived rows. Forced rollback to schema 2 drops the index and keeps memories.
- Search filters for `evidence_id`, `since`, and `until`, plus ranker metadata on `/organism/memories/search`.
- Optional AES-GCM field encryption for continuity JSON, evidence bodies, and organism memory text. A 32-byte key is read from a file. `gaia data-key` creates one and refuses to overwrite it.
- Explicit session ids are adopted by the runtime and restored from the continuity journal after a restart.
- `cryptography` as a runtime dependency for that cipher. The hash chain remains tamper-evident and is not cryptographic immutability.
- Opt-in Memory Organism and evidence ledger (`gaia.organism`, `gaia.evidence`) in one local SQLite file.
- Evidence schema v1 with insert-only headers, separate bodies, and purge receipts that preserve the hash chain.
- Organism schema v1 with working, episodic, semantic, procedural, correction, project, simulation, and autobiographical memories.
- Promotion from episodic records through candidate and validation to approval, with refusals for untrusted instructions and simulation-to-fact promotion.
- Corrections, contradiction links, deletion that keeps content hashes, BM25 retrieval, and owner export.
- Kernel outcome recording with secret-assignment redaction when `organism_path` is set.
- `/organism` routes and `gaia organism` inspection. `gaia run` and `gaia serve` accept `--organism-db`.
- Published continuity checkpoints are cited as evidence digests when both the journal and the organism are configured. Checkpoint payloads are not copied.
- Forced schema rollback to version 0 for organism tables and, separately, for evidence tables. Each rollback leaves the other tables in the same SQLite file.
- Opt-in cognitive continuity journal (`gaia.continuity`) backed by local SQLite.
- Versioned schema v1 and a forced downgrade to an empty schema version 0.
- Validated task state machine, append-only transitions, and hash-linked checkpoints.
- Recovery that interrupts in-flight work, quarantines unpublished or corrupt snapshots, redacts secrets, and revokes approvals.
- Process-local approval grants, work branches, resume, audit export, and live goal deletion.
- Kernel and CLI wiring via `continuity_path` / `--continuity-db`, plus `/kernel/continuity/*` routes.
- `gaia continuity` inspects an existing journal and does not run recovery.

### Notes

- Continuity and the Memory Organism are not enabled for the default in-memory runtime.
- Field encryption is off until a data key is configured. Attaching a key seals existing plaintext fields. A missing or wrong key does not return sealed text and does not quarantine checkpoints.
- The light client is not part of this work. It waits until the local platform milestones are further along.
- Checkpoint hashes and evidence header hashes detect corruption and naive tampering. They are not cryptographic immutability.
- Hybrid and BM25 scores are uncalibrated retrieval weights, not probabilities. Character n-grams are lexical features, not embeddings.
- Approval of organism memory cannot change security policy.
- No new third-party dependencies were added. SQLite and hashing use the Python standard library.
