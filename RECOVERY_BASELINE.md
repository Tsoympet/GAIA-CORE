# GAIA Recovery Baseline R0

## Purpose

This branch begins the controlled recovery of the GAIA repository after repeated merge accumulation introduced duplicate class definitions, conflicting schemas, unreachable code, malformed aggregation structures, repeated agent execution, stale tests, and duplicated status documentation.

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
- normalizes the implementation plan, phase status, and memory documentation;
- adds GitHub Actions checks for compilation, Ruff, mypy, and pytest.

No external tools, cloud model providers, autonomous actions, physical actions, or self-modification are enabled by this recovery.

## Invariants

1. A graph node is executed exactly once per execution attempt.
2. Duplicate node identifiers, missing dependencies, and cycles are rejected.
3. Risky capabilities remain permission-gated.
4. Local model and tool profiles remain routing metadata only.
5. Reflection is internal and cannot execute external actions.
6. Every completed run records task and reflection memory events.
7. Approved memory deletion removes both source records and searchable indexed derivatives.
8. Recovery changes do not grant new autonomy or external-effect permissions.
9. New cognitive architecture work remains blocked until validation is green.

## Remaining recovery gates

- Run the complete compile, lint, type-check, unit, integration, and API smoke suites in CI.
- Repair all validation failures.
- Inspect remaining source, test, configuration, and documentation files for merge fragments.
- Verify memory and workspace APIs after the deletion change.
- Establish a versioned clean baseline before implementing the Cognitive Kernel, Cognitive Continuity, Memory Organism, Living Project Intelligence, GAIA Forge, or Research Laboratory.
