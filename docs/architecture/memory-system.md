# Memory System

GAIA's current memory foundation is local-first and divided into three compatible layers:

1. Runtime event memory for orchestration and reflection events.
2. Scoped Phase 4 memory for project, user, session, and timeline records.
3. Durable workspace metadata persisted in local SQLite.

This is a recovery-stage foundation, not the final Memory Organism architecture.

## Current Phase 4 capabilities

The scoped memory manager provides:

- project, user, session, and timeline scopes;
- local in-memory vector indexing and retrieval;
- symbolic fact storage;
- retention-policy checks;
- owner consent grant and revoke state;
- owner export grouped by scope;
- human-reviewable deletion requests;
- deletion of both scoped records and their indexed vector derivatives after approval.

The workspace store provides:

- local SQLite persistence;
- workspace create, list, and get operations;
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

## Safety rules

- Revoked consent blocks new memory writes for that owner.
- Deletion is review-gated.
- Approved deletion removes the scoped source record and its indexed derivative.
- Export returns retained records grouped by scope.
- The bootstrap vector store is in-memory and performs no external API calls.
- Workspace persistence uses a local SQLite file and performs no network I/O.
- Simulation memory must remain separate from validated factual memory in later phases.

## Remaining work

- durable SQLite/PostgreSQL persistence for memory records;
- workspace-scoped memory binding and timeline events;
- provenance, confidence, contradiction, and derived-record lineage;
- audit events connected to the security ledger;
- production vector backend adapters;
- complete derived-data deletion across summaries, caches, backups, and future graph stores;
- migration, backup, restore, and integrity-check workflows;
- the differentiated Memory Organism defined in the GAIA implementation plan.
