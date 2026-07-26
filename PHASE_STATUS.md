# GAIA Phase Status

## Recovery state

The repository is in **Recovery R0**. New cognitive capabilities remain blocked until the existing foundation is coherent, testable, and protected by validation gates.

The recovery branch is `agent/recover-orchestrator-baseline` and is reviewed through draft pull request #16.

The complete post-recovery implementation backlog and completion standard are recorded in `CAPABILITY_IMPLEMENTATION_REGISTER.md`.

## R0.1 — Orchestration baseline

Completed on the recovery branch:

- one canonical `TaskStep` and `TaskPlan` contract;
- deterministic dependency-ordered task planning;
- validated DAG construction with duplicate-ID, missing-dependency, and cycle rejection;
- one capability-router implementation with local-first model/tool metadata;
- permission-gated execution modes for risky capabilities;
- exactly one selected-agent invocation per task node;
- coherent aggregation, route/status artifacts, reflection, and memory events;
- regression coverage for single node execution.

## R0.2 — Memory, tests, documentation, and CI

Completed on the recovery branch:

- Phase 4 memory/workspace source inspected for merge duplication;
- stale duplicate Phase 3 test contract removed;
- core pipeline expectations aligned with the single-execution invariant;
- approved memory deletion removes indexed vector derivatives as well as scoped records;
- vector store deletion and count contracts added;
- recovery, memory, orchestration, and implementation documents normalized;
- GitHub Actions validation added for compilation, linting, typing, and tests.

## R0.3 — Runtime, API, agents, and security

Completed or in progress:

- duplicate FastAPI method/path registrations removed;
- runtime event-memory status separated from scoped memory status;
- redundant pytest async compatibility hook removed;
- broken legacy `GaiaCore` facade replaced with a wrapper over the canonical runtime;
- obsolete second orchestration framework removed;
- obsolete standalone agent framework removed while preserving specialist agents in the canonical registry;
- functional command, file, and network guards repaired;
- duplicate placeholder guard modules removed;
- permission and API kill-switch state unified;
- security package exports normalized;
- API services bound to the runtime permission manager and security policy;
- route uniqueness, shared kill-switch, facade, memory deletion, execution-count, and guard regression tests added;
- authoritative capability implementation register created;
- obsolete missing-files report replaced with a current implementation gap assessment.

## Current working foundation

### Runtime and API

- FastAPI and CLI bootstrap;
- canonical `GaiaRuntime` composition root;
- high-level `GaiaCore` compatibility facade;
- app-scoped API services sharing runtime security state;
- health, version, task, planning, agent, capability, memory, workspace, security, voice, and audio routes.

### Orchestration

- structured task steps;
- dependency-aware validated task graph;
- capability routing;
- deterministic local agent execution;
- result aggregation;
- internal metacognitive reflection;
- auditable route and status artifacts.

### Memory and workspaces

- append-only runtime event memory;
- project, user, session, and timeline scopes;
- local in-memory vector indexing and retrieval;
- symbolic facts;
- retention checks;
- owner consent grant/revoke state;
- export grouped by scope;
- review-gated deletion including indexed derivatives;
- memory review APIs;
- durable local SQLite workspace metadata and lifecycle APIs.

### Security

- objective security policy;
- deny-by-default permission manager;
- explicit human approval for risky permissions;
- functional command, file, and network guards;
- audit events;
- one shared autonomy kill switch;
- API controls and runtime status using the same security state.

### Models, agents, voice, and desktop

- local-first model catalog and disabled-by-default cloud fallback;
- canonical agent registry with specialist capability agents;
- synthetic voice abstractions and safety controls;
- Tauri/React desktop shell and voice panels.

## Validation gate

Recovery R0 is complete only when the branch passes:

1. Python bytecode compilation;
2. Ruff checks;
3. strict mypy checks;
4. the complete pytest suite;
5. FastAPI route smoke tests;
6. a repository-wide duplicate-definition and stale-import scan;
7. review of remaining overlapping PR files;
8. a versioned clean-baseline release review.

## Implementation commitment after R0

The unfinished capabilities listed in `CAPABILITY_IMPLEMENTATION_REGISTER.md` must be implemented as real code with runtime wiring, persistence, migrations, security, tests, APIs, desktop integration, and rollback where applicable. Documentation, placeholders, static responses, and empty panels do not count as completed features.

## Next action

Finish the remaining R0.3 scan, resolve validation failures, update PR #16 with the complete recovery record, and issue the first clean versioned GAIA baseline. Then begin R1 with the Cognitive Kernel.
