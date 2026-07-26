# GAIA Phase Status

## Recovery state

The repository is in **Recovery R0**. New cognitive capabilities remain blocked until the existing foundation is coherent, testable, and protected by CI.

The recovery branch is `agent/recover-orchestrator-baseline` and is reviewed through draft pull request #16.

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

Completed or in progress:

- Phase 4 memory/workspace source inspected for merge duplication;
- stale duplicate Phase 3 test contract removed;
- core pipeline expectations aligned with the single-execution invariant;
- approved memory deletion now removes indexed vector derivatives as well as scoped records;
- recovery and architecture documents normalized;
- GitHub Actions validation added for compilation, linting, typing, and tests.

## Current implemented foundation

### Phase 1/2 — Runtime foundation

- FastAPI and CLI bootstrap;
- local-first model registry and disabled-by-default cloud fallback;
- agent and capability registries;
- initial security policy, permission records, guards, audit scaffolding, and kill switch;
- Tauri/React desktop shell;
- synthetic voice abstractions and API scaffolding.

### Phase 3 — Orchestration

- structured task steps;
- dependency-aware task graph;
- capability routing;
- deterministic local agent execution;
- result aggregation;
- internal metacognitive reflection;
- auditable route and status artifacts.

### Phase 4 — Memory and workspaces

- project, user, session, and timeline scopes;
- local in-memory vector indexing and retrieval;
- symbolic facts;
- retention checks;
- owner consent grant/revoke state;
- export grouped by scope;
- review-gated deletion including indexed derivatives;
- memory review APIs;
- durable local SQLite workspace metadata and lifecycle APIs.

## Validation gate

Recovery R0 is complete only when the branch passes:

1. Python bytecode compilation;
2. Ruff checks;
3. strict mypy checks;
4. the complete pytest suite;
5. FastAPI route smoke tests;
6. a repository-wide duplicate-definition scan;
7. review of all remaining overlapping PR files.

## Work blocked until R0 is green

Do not add the Cognitive Kernel, Cognitive Continuity, Memory Organism, Living Project Intelligence, GAIA Forge, Research Laboratory, autonomous tools, or physical-AI adapters before the recovery baseline is validated.

## Next action

Run CI on PR #16, repair any remaining failures, scan untouched source and test files for merge artifacts, and issue the first versioned clean GAIA baseline.
