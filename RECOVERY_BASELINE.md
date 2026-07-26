# GAIA Recovery Baseline R0

## Status

Recovery R0 is validated on branch `agent/recover-orchestrator-baseline` through pull request #16.

Validated code head: `33fc630c184ad3cd7956ef5b96de815cdf9f0ce7`  
Successful GitHub Actions run: `30212673071`

The recovery baseline is the stable parent for subsequent Cognitive Operating System implementation work. It is not the final GAIA product.

## Purpose

This branch performs controlled recovery of the GAIA repository after repeated merge accumulation introduced duplicate class definitions, conflicting schemas, unreachable code, malformed aggregation, repeated agent execution, stale tests, parallel incompatible frameworks, duplicate API routes, incomplete deletion, and split security state.

Recovery establishes one coherent platform contract so missing capabilities can be implemented without adding further parallel runtimes, fake integrations, or ungoverned placeholders.

## R0.1 — Orchestration recovery

The first recovery batch replaced the corrupted orchestration core with one coherent deterministic implementation:

- task planning;
- task graph construction and validation;
- capability routing;
- one-execution-per-node enforcement;
- result aggregation;
- reflection integration;
- orchestration regression tests.

## R0.2 — Memory and validation recovery

The second recovery batch:

- inspected the Phase 4 memory/workspace overlap set;
- removed a stale duplicate Phase 3 test contract;
- aligned core pipeline tests with the one-execution invariant;
- ensured approved memory deletion also removes vector-index derivatives;
- added stable vector deletion and count interfaces;
- normalized the implementation plan, phase status, and memory/orchestration documentation;
- added GitHub Actions checks for compilation, Ruff, strict mypy, and pytest;
- preserved complete diagnostics and an exact source snapshot as CI artifacts.

## R0.3 — Runtime, API, agent, and security recovery

The third recovery batch:

- removed duplicate FastAPI method/path registrations;
- separated runtime event-memory status from scoped memory status;
- removed the redundant pytest async compatibility hook;
- replaced the broken legacy `GaiaCore` facade with a wrapper over the canonical runtime;
- removed the unused second orchestration framework;
- removed the obsolete standalone agent framework while retaining specialist capability agents in the canonical registry;
- repaired functional command, file, and network guards;
- removed duplicate placeholder guard modules;
- unified permission-manager and API kill-switch state;
- added approval-gated secret-read and self-modification permissions;
- normalized security exports and API dependency wiring;
- removed duplicate task-node routing fields;
- repaired capability-registry and specialist-agent typing contracts;
- replaced dynamic execution-context replacement with an explicit typed derivation API;
- added API-route uniqueness, shared kill-switch, security-guard, facade, memory-deletion, secret, self-modification, and one-execution regression coverage;
- created the authoritative capability implementation register and current gap report.

No external tools, cloud model providers, autonomous external actions, physical actions, or unapproved self-modification are enabled by this recovery.

## Validated checks

The successful validation run completed all configured gates in one job:

1. project and development dependency installation;
2. Python source and test bytecode compilation;
3. Ruff checks across `src` and `tests`;
4. strict mypy checks across the `gaia` package;
5. the complete pytest suite, with 54 passing tests;
6. validation artifact creation containing logs and the exact source snapshot.

## Invariants

1. A graph node is executed exactly once per execution attempt.
2. Duplicate node identifiers, missing dependencies, and cycles are rejected.
3. Risky capabilities remain permission-gated and require explicit approval.
4. Local model and tool profiles remain routing metadata until real guarded adapters are implemented.
5. Reflection is internal and cannot execute external actions.
6. Every completed run records task and reflection memory events.
7. Approved memory deletion removes both source records and searchable indexed derivatives.
8. API security controls and permission checks use the same kill-switch object.
9. One canonical runtime, orchestration, agent, memory-purpose, and security contract is maintained.
10. Recovery changes do not grant new autonomy or external-effect permissions.
11. Missing features must be implemented as real code under the completion standard in `CAPABILITY_IMPLEMENTATION_REGISTER.md`.
12. The recovery branch remains stable; new feature development proceeds on separate branches.

## Next phase

R1 implements the Cognitive Kernel, including goal and task state, context, resource budgets, verification, cancellation, interruption, lifecycle coordination, and policy integration. Later phases implement Cognitive Continuity, the Memory Organism, Living Project Intelligence, GAIA Forge, the Research Laboratory, real model/tool adapters, voice, multimodality, and the desktop mission-control interface.
