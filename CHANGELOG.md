# Changelog

## Unreleased

### Added

- Opt-in Memory Organism and evidence ledger (`gaia.organism`, `gaia.evidence`) in one local SQLite file.
- Evidence schema v1 with insert-only headers, separate bodies, and purge receipts that preserve the hash chain.
- Organism schema v1 with working, episodic, semantic, procedural, correction, project, simulation, and autobiographical memories.
- Promotion from episodic records through candidate and validation to approval, with refusals for untrusted instructions and simulation-to-fact promotion.
- Corrections, contradiction links, deletion that keeps content hashes, BM25 retrieval, and owner export.
- Kernel outcome recording with secret-assignment redaction when `organism_path` is set.
- `/organism` routes and `gaia organism` inspection. `gaia run` and `gaia serve` accept `--organism-db`.
- Published continuity checkpoints are cited as evidence digests when both the journal and the organism are configured. Checkpoint payloads are not copied.
- Opt-in cognitive continuity journal (`gaia.continuity`) backed by local SQLite.
- Versioned schema v1 and a forced downgrade to an empty schema version 0.
- Validated task state machine, append-only transitions, and hash-linked checkpoints.
- Recovery that interrupts in-flight work, quarantines unpublished or corrupt snapshots, redacts secrets, and revokes approvals.
- Process-local approval grants, work branches, resume, audit export, and live goal deletion.
- Kernel and CLI wiring via `continuity_path` / `--continuity-db`, plus `/kernel/continuity/*` routes.
- `gaia continuity` inspects an existing journal and does not run recovery.

### Notes

- Continuity and the Memory Organism are not enabled for the default in-memory runtime.
- Checkpoint hashes and evidence header hashes detect corruption and naive tampering. They are not cryptographic immutability.
- BM25 scores are uncalibrated retrieval weights, not probabilities.
- Approval of organism memory cannot change security policy.
- No new third-party dependencies were added. SQLite and hashing use the Python standard library.
