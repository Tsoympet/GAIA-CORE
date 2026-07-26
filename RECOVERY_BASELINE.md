# GAIA Recovery Baseline R0

## Purpose

This branch begins the controlled recovery of the GAIA repository after repeated
merge accumulation introduced duplicate class definitions, conflicting schemas,
unreachable code, malformed aggregation structures, and repeated agent
execution.

## Scope of R0.1

This recovery change replaces the corrupted Phase 3 orchestration core with one
coherent deterministic implementation:

- task planning;
- task graph construction and validation;
- capability routing;
- one-execution-per-node enforcement;
- result aggregation;
- reflection integration;
- orchestration regression tests.

No external tools, model providers, autonomous actions, or self-modification are
enabled by this recovery.

## Invariants

1. A graph node is executed no more than once per execution attempt.
2. Duplicate node identifiers and cyclic dependencies are rejected.
3. Risky capabilities remain permission-gated.
4. Local model and tool profiles remain routing metadata only.
5. Reflection is internal and cannot execute external actions.
6. Every completed run records task and reflection memory events.
7. The recovery branch does not alter Phase 4 workspace or memory APIs.

## Next recovery gates

- Run the complete compile, lint, type-check, unit, integration, and API smoke
  suites in CI.
- Inspect the remaining repository for duplicate merge fragments.
- Normalize duplicated roadmap and implementation-plan documentation.
- Establish a versioned clean baseline before implementing the Cognitive Kernel,
  Cognitive Continuity, Memory Organism, GAIA Forge, or Research Laboratory.
