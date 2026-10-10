# ADR 0002: Local SQLite Memory Organism and evidence ledger

## Status

Accepted for the R3 memory milestone. The capability remains partial.

## Context

Phase 4 memory is an in-memory scoped store. Continuity persists kernel goals
and checkpoints in a separate SQLite journal. The master architecture asks for
a Memory Organism and an evidence ledger with promotion rules. The repository
does not depend on PostgreSQL, Redis, Chroma, or a vector database.

## Decision

Persist evidence and organism memories in one opt-in SQLite file addressed by
`organism_path`.

- Evidence headers are insert-only. Bodies are a separate table so retention
  purge can remove text without rewriting the header hash chain.
- Organism memories cite evidence ids. They do not replace evidence.
- Promotion is explicit: episodic-class record, candidate, validation, then
  approval. Approval always stores `policy_effect = "none"`.
- Untrusted instruction-like document, tool, and model text cannot become a
  candidate. Simulation content cannot become factual knowledge.
- Default retrieval returns recorded observations and approved knowledge.
- No new third-party database dependency is added.

The continuity journal stays a separate path. A runtime that configures both
paths cites each published checkpoint in the evidence ledger by digest. The
payload remains in the continuity journal.

## Consequences

- Operators can restart a configured runtime and reload memories and evidence.
- Secret assignments in kernel outcomes are redacted before they are stored.
- The evidence hash chain is tamper-evident against accidental corruption and
  naive payload edits. It is not cryptographic immutability.
- Encryption at rest, embedding retrieval, and desktop presentation are not
  provided by this decision.
- Phase 4 `/memory` routes continue to use the in-memory manager.

## Rollback

Stop the runtime. Restore a copy of the SQLite file. There is no
`rollback_schema` helper for these tables. Application code from this
milestone can be reverted; older runtimes ignore the file unless
`organism_path` is set.
