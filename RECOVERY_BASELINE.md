# GAIA Recovery Baseline R0

## Purpose

This branch performs controlled recovery of the GAIA repository after repeated merge accumulation introduced duplicate class definitions, conflicting schemas, unreachable code, malformed aggregation, repeated agent execution, stale tests, parallel incompatible frameworks, duplicate API routes, incomplete deletion, and split security state.

Recovery is not the final project objective. It establishes one coherent platform contract so the missing Cognitive Operating System capabilities can be implemented without adding further parallel runtimes or placeholders.

## R0.1 — Orchestration recovery

The first recovery batch replaces the corrupted Phase 3 orchestration core with one coherent deterministic implementation:

- task planning;
- task graph construction and validation;
- capability routing;
- one-execution-per-node enforcement;
- result aggregation;
- reflection integration;
- orchestration regression tests.

## R0.2 — Memory and validation recovery

The second recovery batch:

- inspects the Phase 4 memory/workspace overlap set;
- removes a stale duplicate Phase 3 test contract;
- aligns core pipeline tests with the one-execution invariant;
- ensures approved memory deletion also removes vector-index derivatives;
- adds stable vector deletion and count interfaces;
- normalizes the implementation plan, phase status, and memory/orchestration documentation;
- adds GitHub Actions checks for compilation, Ruff, mypy, and pytest.

## R0.3 — Runtime, API, agent, and security recovery

The third recovery batch:

- removes duplicate FastAPI method/path registrations;
- separates runtime event-memory status from scoped memory status;
- removes the redundant pytest async compatibility hook;
- replaces the broken legacy `GaiaCore` facade with a wrapper over the canonical runtime;
- removes the unused second orchestration framework;
- removes the obsolete standalone agent framework while retaining specialist capability agents in the canonical registry;
- repairs functional command, file, and network guards;
- removes duplicate placeholder guard modules;
- unifies permission-manager and API kill-switch state;
- normalizes security exports and API dependency wiring;
- adds API-route uniqueness, shared kill-switch, security-guard, facade, memory-deletion, and one-execution regression coverage;
- creates the authoritative capability implementation register and current gap report.

No external tools, cloud model providers, autonomous external actions, physical actions, or self-modification are enabled by this recovery.

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
11. New cognitive architecture work remains blocked until validation is green.
12. After R0, missing features must be implemented as real code under the completion standard in `CAPABILITY_IMPLEMENTATION_REGISTER.md`.

## Remaining recovery gates

- Run complete compile, lint, type-check, unit, integration, and API smoke suites.
- Repair all validation failures.
- Inspect remaining source, test, configuration, desktop, and documentation files for stale imports or parallel contracts.
- Verify memory, workspace, security, voice, and model APIs after recovery changes.
- Review the full PR diff for accidental feature removal.
- Establish a versioned clean baseline before implementing the Cognitive Kernel, Cognitive Continuity, Memory Organism, Living Project Intelligence, GAIA Forge, or Research Laboratory.
