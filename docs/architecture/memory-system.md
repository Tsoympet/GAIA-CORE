# Memory System

GAIA's memory system is local-first and currently split into three compatible
layers:

1. Runtime event memory for orchestration events.
2. Scoped Phase 4 memory for project, user, session, and timeline records.
3. Durable workspace metadata persisted in local SQLite.

## Phase 4 Capabilities

The scoped memory manager provides:

- project, user, session, and timeline scopes
- local in-memory vector indexing and retrieval
- symbolic fact storage
- retention policy checks
- owner consent grant/revoke state
- owner export grouped by scope
- human-reviewable deletion requests before records are removed

The workspace store provides:

- local SQLite persistence
- workspace create/list/get lifecycle operations
- JSON metadata storage
- operator status showing database path, workspace count, and durability

## User-Facing Review APIs

The FastAPI memory routes expose review controls for user-governed memory:

- `GET /memory/status`
- `POST /memory`
- `GET /memory/review?owner_id=...&scope=...`
- `GET /memory/export/{owner_id}`
- `POST /memory/consent/grant`
- `POST /memory/consent/revoke`
- `POST /memory/deletion-requests`
- `POST /memory/deletion-requests/{request_id}/review`

The workspace routes expose durable local workspace metadata:

- `GET /workspaces/status`
- `POST /workspaces`
- `GET /workspaces`
- `GET /workspaces/{workspace_id}`

## Safety Rules

- Revoked consent blocks new memory writes for that owner.
- Deletion is not immediate; a deletion request must be reviewed and approved.
- Export returns retained records grouped by scope.
- The bootstrap vector store is in-memory only and does not call external APIs.
- Workspace persistence uses a local SQLite file and does not perform network I/O.

## Remaining Phase 4 Work

- Durable SQLite/PostgreSQL persistence for memory records themselves.
- Workspace-scoped memory binding and workspace timeline events.
- Memory audit events connected to the security audit log.
- Production vector backend adapters.
- Backup/restore workflows and migration scripts.
