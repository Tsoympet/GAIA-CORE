# GAIA Phase Status

## Recovery state

**Recovery R0 is validated on the recovery branch.**

Branch: `agent/recover-orchestrator-baseline`  
Review: pull request #16  
Validated head: `33fc630c184ad3cd7956ef5b96de815cdf9f0ce7`

The complete post-recovery implementation backlog and completion standard are recorded in `CAPABILITY_IMPLEMENTATION_REGISTER.md`.

## R0.1 — Orchestration baseline

Completed:

- one canonical `TaskStep` and `TaskPlan` contract;
- deterministic dependency-ordered task planning;
- validated DAG construction with duplicate-ID, missing-dependency, and cycle rejection;
- one capability-router implementation with local-first model/tool metadata;
- permission-gated execution modes for risky capabilities;
- exactly one selected-agent invocation per task node;
- coherent aggregation, route/status artifacts, reflection, and memory events;
- regression coverage for single node execution.

## R0.2 — Memory, tests, documentation, and CI

Completed:

- Phase 4 memory/workspace source inspected for merge duplication;
- stale duplicate Phase 3 test contract removed;
- core pipeline expectations aligned with the single-execution invariant;
- approved memory deletion removes indexed vector derivatives as well as scoped records;
- vector store deletion and count contracts added;
- recovery, memory, orchestration, and implementation documents normalized;
- GitHub Actions validation added for compilation, linting, typing, tests, diagnostics, and source snapshots.

## R0.3 — Runtime, API, agents, and security

Completed:

- duplicate FastAPI method/path registrations removed;
- runtime event-memory status separated from scoped memory status;
- redundant pytest async compatibility hook removed;
- broken legacy `GaiaCore` facade replaced with a wrapper over the canonical runtime;
- obsolete second orchestration framework removed;
- obsolete standalone agent framework removed while preserving specialist agents in the canonical registry;
- functional command, file, and network guards repaired;
- duplicate placeholder guard modules removed;
- permission and API kill-switch state unified;
- self-modification and secret-read permissions repaired and approval-gated;
- security package exports normalized;
- API services bound to the runtime permission manager and security policy;
- duplicate task-node routing fields removed;
- capability-registry type shadowing removed;
- strict typing restored for agent capabilities and execution-context derivation;
- route uniqueness, shared kill-switch, facade, memory deletion, execution-count, secret, self-modification, and guard regression tests added;
- authoritative capability implementation register created;
- obsolete missing-files report replaced with a current implementation gap assessment.

## Validation result

GitHub Actions run `30212673071` completed successfully on the validated head.

- dependency installation: passed;
- Python bytecode compilation: passed;
- Ruff repository checks: passed;
- strict mypy checks: passed;
- complete pytest suite: **54 passed**;
- validation diagnostics artifact: generated successfully.

The current test environment reports one upstream Starlette/httpx deprecation warning. It is not a failing GAIA test and should be tracked during dependency maintenance.

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
- approval-gated secret reads and self-modification;
- audit events;
- one shared autonomy kill switch;
- API controls and runtime status using the same security state.

### Models, agents, voice, and desktop

- local-first model catalog and disabled-by-default cloud fallback;
- canonical agent registry with specialist capability agents;
- synthetic voice abstractions and safety controls;
- Tauri/React desktop shell and voice panels.

## Implementation commitment after R0

The unfinished capabilities listed in `CAPABILITY_IMPLEMENTATION_REGISTER.md` must be implemented as real code with runtime wiring, persistence, migrations, security, tests, APIs, desktop integration, and rollback where applicable. Documentation, placeholders, static responses, and empty panels do not count as completed features.

## R1 — Cognitive Kernel foundation

Merged to `main` by pull request #20 (`2a9b43b`).

Completed in that foundation slice:

- `gaia.kernel` package with typed goal, context, budget, policy, verification, and interrupt modules;
- `CognitiveKernel` composition root wrapping the recovered orchestrator;
- runtime task submission routed through the kernel control plane;
- operator API under `/kernel/*` for status, goals, cancel, interrupts, and kernel task submission;
- unit and integration coverage for lifecycle, budgets, verification, policy gating, and API routes.

The kernel remains `PARTIAL` until streaming run events, desktop mission-control surfaces, and the rest of the completion standard are done. Durable goal and context state is now available only when a continuity journal is configured.

## R2 — Cognitive Continuity

Partial. Opt-in local SQLite journal in `gaia.continuity`.

Completed in this slice:

- versioned schema with an explicit downgrade to an empty version 0;
- validated task state machine and append-only transitions;
- crash-safe checkpoint publication and hash-chain verification;
- recovery that interrupts in-flight work, quarantines unpublished or corrupt snapshots, and revokes approvals;
- redaction of credential and approval-token fields before persistence and again on recovery;
- process-local approval grants that are not reusable after restart;
- work-branch records bound to a verified checkpoint;
- resume of interrupted work through a fresh policy check;
- operator API, audit export, live-goal deletion, and `gaia continuity` inspection;
- a pid lock that refuses to recover a journal held by another live process.

Still required before Cognitive Continuity can be marked `IMPLEMENTED`:

- streaming run events;
- desktop mission-control surfaces;
- a durable session store beyond the session id recorded on each goal.

Field encryption is available when a 32-byte data key is configured. It is not whole-file encryption, and the hash chain is still not cryptographic immutability.

The hash chain is tamper-evident for accidental corruption. It is not cryptographic immutability.

## R3 — Memory Organism and Evidence Ledger

Partial. Opt-in local SQLite store in `gaia.evidence` and `gaia.organism`.

Completed in this slice:

- schema version 1 for evidence headers, bodies, purge receipts, memories, events, and contradiction links;
- append-only evidence headers whose hash chain still verifies after a body purge;
- promotion from episodic-class records through candidate, validation, and approval;
- refusals for untrusted instruction-like text and for promoting simulation into factual knowledge;
- corrections that append a new memory and leave the original content and hash unchanged;
- deletion that clears text, keeps `content_sha256`, and rejects non-approved children;
- default BM25 retrieval of recorded and approved memories, with strict project isolation;
- kernel outcome recording with secret-assignment redaction;
- citation of published continuity checkpoints as evidence digests when both stores are configured;
- forced schema rollback to version 0 for organism tables and, separately, for evidence tables;
- `/organism` routes and `gaia organism` inspection;
- optional AES-GCM field encryption for evidence bodies, memory text, and continuity secret fields when a data key is configured.

The Phase 4 scoped memory manager is unchanged and still in process memory.

Still required before the Memory Organism can be marked `IMPLEMENTED`:

- retrieval beyond uncalibrated BM25;
- user-preference, identity, and timeline categories;
- desktop surfaces.

Field encryption seals evidence bodies, memory text, and continuity secret fields when a data key is configured. Opening an encrypted file without that key fails closed.

`cryptographic_immutability` is false. See `docs/architecture/memory_organism.md`.

## Next phase

Finish the remaining local platform gaps: a durable session store, retrieval beyond BM25, and the user-preference, identity, and timeline categories. Living Project Intelligence comes after those. The light client waits until this local platform work is in place. Do not replace the Phase 4 memory manager or the continuity journal. Do not open a second persistence path for goals or task state.
