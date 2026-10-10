# Memory Organism and Evidence Ledger (R3, partial)

The Memory Organism is an opt-in local SQLite store. It is separate from the
in-memory Phase 4 scoped memory manager and from the continuity journal.
Unconfigured runtimes report `memory_organism` as `unavailable`.

Evidence headers and organism memories share one file when `organism_path` is
set. They use different tables and different migration tables
(`evidence_schema_migrations`, `organism_schema_migrations`). Both are schema
version 1.

## Promotion

Raw evidence is stored first. A memory may cite that evidence. It does not
replace the evidence body.

Allowed path:

1. Append evidence (`user`, `operator`, `tool`, `model`, `document`, or `system`).
2. Record an episodic-class memory: `episodic`, `working`, `autobiographical`,
   `project`, or `simulation`.
3. Propose a candidate in `semantic`, `procedural`, `project`, or `simulation`.
   The candidate must cite at least one source memory.
4. Validate the candidate. Validation does not approve it.
5. Approve a validated memory. `policy_effect` stays `none`.

Refusals that the tests cover:

- Instruction-like text from a `document`, `tool`, or `model` source is stored
  as episodic with `untrusted_instruction` set. It cannot become a candidate.
- The candidate text itself cannot contain the same instruction markers.
- Simulation memory cannot be cited as the source of a factual candidate.
- Approval of a simulation memory, if reached, does not set
  `approved_knowledge`.
- A candidate cannot be approved before validation.
- Deleted memories cannot support a new candidate.

Kernel task outcomes are recorded as `system` evidence plus an autobiographical
memory. Secret assignments such as `token=...` are redacted before storage.
That recording does not grant authority and does not change security policy.

## Retrieval

Default search returns `recorded` and `approved` memories only. It excludes
deleted text, candidates, validated-but-unapproved memories, rejected memories,
contradicted memories, stale memories, simulation memories, and untrusted
instructions. Callers opt in to those classes with explicit flags.

A project filter is strict. Global memories are included only when
`include_global` is set and the memory has no project id.

Ranking uses BM25, confidence, and recency. The score is an uncalibrated
retrieval weight. It is not a probability and it is not a calibrated
confidence.

Corrections are recorded memories, so they are searchable. The original text
stays unchanged and is marked contradicted, which hides it from the default
search.

## Evidence integrity

Header rows are insert-only. Bodies live in `evidence_bodies`. An expired
purge deletes the body and writes an `evidence_purges` receipt. The header
hash chain still verifies after that purge. Editing a stored header or hash
makes `verify_chain()` fail and the capability status becomes `degraded`.

`cryptographic_immutability` is always false. A privileged local writer can
recompute the chain. The ledger detects corruption and naive edits.

## API and CLI

Routes under `/organism` return status `unavailable` with HTTP 200 when no
organism is configured. Mutating routes return HTTP 409 in that case.

- `GET /organism/status`
- `POST /organism/evidence`
- `GET /organism/evidence/{evidence_id}`
- `GET /organism/evidence`
- `POST /organism/memories`
- `POST /organism/memories/candidates`
- `POST /organism/memories/{memory_id}/validate`
- `POST /organism/memories/{memory_id}/approve`
- `POST /organism/memories/{memory_id}/correct`
- `GET /organism/memories/search`
- `POST /organism/memories/{memory_id}/delete`
- `GET /organism/export/{owner_id}`

`gaia organism --db <path>` inspects an existing file and does not create one
when the file is absent. `gaia run` and `gaia serve` accept `--organism-db`.

Existing `/memory` routes are unchanged.

## Deletion

Deletion clears memory text and sets status `deleted`. `content_sha256` is
kept. Evidence bodies are not deleted by a memory deletion. Non-approved
children that name the deleted memory as parent become `rejected`.

## Current limitations

- Not encrypted at rest.
- No hybrid or embedding retrieval. BM25 is the only ranker.
- No user-preference, identity, or timeline category beyond autobiographical
  kernel notes.
- When both `continuity_path` and `organism_path` are set, each published
  checkpoint is cited as evidence. The citation stores the checkpoint id,
  payload digest, parent id, reason, and kernel id. It does not store the
  checkpoint payload. Binding is not automatic for an organism opened on its
  own.
- Phase 4 scoped memory remains in process memory.
- Desktop mission control is not wired to these routes.
- This capability stays `PARTIAL`.

## Rollback

`MemoryOrganism.rollback_schema(0, force=True)` drops organism memories,
events, and contradiction links. It keeps evidence headers and any continuity
tables in the same file. `EvidenceLedger.rollback_schema(0, force=True)` drops
evidence headers, bodies, and purge receipts. It keeps organism and continuity
tables. Both refuse when rows exist unless `force` is true. The next open
migrates the dropped group back to an empty version 1.

Copy the SQLite file before a forced downgrade. Older runtimes do not open
the file unless `organism_path` is set.
