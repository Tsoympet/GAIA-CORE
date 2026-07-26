# Cognitive Kernel

## Status

R1 initial implementation: partial and executable.

The Cognitive Kernel is the stable governance layer around GAIA task execution. Models and agents remain replaceable components; goals, execution state, budgets, cancellation, verification, permissions, and auditability belong to the platform.

## Implemented in R1.1

- typed goal lifecycle with validated transitions;
- kernel execution ledger;
- per-task wall-clock and step budgets;
- preflight step-budget rejection;
- cooperative cancellation registry;
- timeout enforcement that cancels the active coroutine;
- deterministic result verification;
- runtime integration for every `TaskRequest`;
- structured kernel artifacts in task responses;
- operator APIs for kernel status, goals, executions, and cancellation;
- unit and integration coverage for lifecycle, budget, timeout, cancellation, verification, and API behavior.

## Current execution path

```text
TaskRequest
  -> CognitiveKernel.begin_execution
  -> goal activation
  -> resource-budget preflight
  -> guarded orchestrator coroutine
     -> cancellation race
     -> wall-clock timeout
  -> verification
  -> execution and goal finalization
  -> kernel evidence attached to response
```

## Safety properties

- a terminal goal cannot be reactivated;
- a task that exceeds its preflight step budget does not execute;
- timeout cancels the active coroutine;
- operator cancellation is cooperative and recorded;
- results are not accepted without structural verification;
- kernel execution state is distinct from model-generated content;
- this phase does not add external tools or new autonomous permissions.

## Remaining R1 work

- durable execution and goal persistence;
- interruption and restart recovery through Cognitive Continuity;
- token, cost, memory, CPU, and GPU metering;
- approval checkpoints inside task graphs;
- streaming kernel events;
- policy-based priority scheduling;
- project-bound goals;
- verifier-agent and evidence-ledger integration;
- desktop mission-control panels.

The capability remains `PARTIAL` until persistence, migrations, recovery, complete resource metering, and desktop controls are implemented.
