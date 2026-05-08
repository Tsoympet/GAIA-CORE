# Memory System

GAIA's memory system is local-first and currently split into two compatible
layers:

1. Runtime event memory for orchestration events.
2. Scoped Phase 4 memory for project, user, session, and timeline records.

## Phase 4 Capabilities

The scoped memory manager provides:

- project, user, session, and timeline scopes
- local in-memory vector indexing and retrieval
- symbolic fact storage
- retention policy checks
- owner consent grant/revoke state
- owner export grouped by scope
- human-reviewable deletion requests before records are removed

## Safety Rules

- Revoked consent blocks new memory writes for that owner.
- Deletion is not immediate; a deletion request must be reviewed and approved.
- Export returns retained records grouped by scope.
- The bootstrap vector store is in-memory only and does not call external APIs.

## Remaining Phase 4 Work

- Durable SQLite/PostgreSQL persistence.
- Workspace lifecycle APIs and workspace-scoped storage.
- Memory audit events connected to the security audit log.
- Production vector backend adapters.
- User-facing memory review, export, and delete endpoints.
