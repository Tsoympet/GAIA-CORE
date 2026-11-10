# Memory System

GAIA's current memory foundation is local-first and divided into three compatible layers:

1. Runtime event memory for orchestration and reflection events.
2. Scoped Phase 4 memory for project, user, session, and timeline records.
3. Durable workspace metadata persisted in local SQLite.

This is a recovery-stage foundation. The opt-in Memory Organism in
`docs/architecture/memory_organism.md` is a separate partial store. It does
not replace the Phase 4 manager described below.

## Current Phase 4 capabilities

The scoped memory manager provides:

- project, user, session, and timeline scopes;
- local SQLite vector indexing and retrieval, with uncalibrated cosine scores;
- symbolic fact storage, with unscoped facts hidden from every owner's list and recall;
- retention-policy checks;
- owner consent grant and revoke state;
- owner export grouped by scope;
- human-reviewable deletion requests;
- deletion of both scoped records and their indexed vector derivatives after approval.

The workspace store provides:

- local SQLite persistence;
- workspace create, list, and get operations;
- task and memory reference links stored beside the workspace row;
- link creation rejects an unknown task or memory id;
- listed links report whether the target still exists;
- JSON metadata storage;
- operator status containing database path, workspace count, and durability state.

## User-facing review APIs

Memory routes:

- `GET /memory/status`
- `POST /memory`
- `GET /memory/review?owner_id=...&scope=...`
- `GET /memory/export/{owner_id}`
- `POST /memory/consent/grant`
- `POST /memory/consent/revoke`
- `POST /memory/deletion-requests`
- `POST /memory/deletion-requests/{request_id}/review`

Workspace routes:

- `GET /workspaces/status`
- `POST /workspaces`
- `GET /workspaces`
- `GET /workspaces/{workspace_id}`
- `POST /workspaces/{workspace_id}/links`
- `GET /workspaces/{workspace_id}/links`

Phase-4 memory text and symbolic facts written through the API are copied into
`.gaia/cognition.sqlite3` as notes. `gaia serve` also stores scoped records and
their hashed n-gram vectors in `.gaia/phase4.sqlite3`, so ranked recall survives
a new process. Cosine scores stay uncalibrated. Symbolic facts themselves stay
in process memory. Dream and metacognition notes use the cognition file and do
not perform external actions.

## Safety rules

- Revoked consent blocks new memory writes for that owner.
- Deletion is review-gated.
- Approved deletion removes the scoped source record and its indexed derivative.
- Export returns retained records grouped by scope.
- The phase-4 vector index is a local SQLite file of hashed n-gram vectors and performs no external API calls. An in-memory store remains available for isolated tests.
- Workspace persistence uses a local SQLite file and performs no network I/O.
- Simulation memory must remain separate from validated factual memory in later phases.

## Remaining work

- PostgreSQL persistence, backup, and restore for memory records;
- workspace-scoped memory binding and timeline events;
- provenance, confidence, contradiction, and derived-record lineage;
- audit events connected to the security ledger;
- production vector backend adapters;
- complete derived-data deletion across summaries, caches, backups, and future graph stores;
- migration, backup, restore, and integrity-check workflows;
- neural embeddings and calibrated confidence for the partial Memory Organism.
  Preference, identity, and timeline categories now live in that organism.
  Hybrid BM25 + character n-gram retrieval is local to that store.
  Phase 4 scoped memory still does not store them.
