# Orchestrator

The GAIA orchestrator is a local-first planner/router/executor/aggregator pipeline inspired conceptually by Microsoft JARVIS/HuggingGPT, but implemented as original typed GAIA primitives.

## Phase 3 pipeline

```text
User request
→ TaskPlanner
→ structured TaskStep list
→ validated TaskGraph DAG
→ CapabilityRouter
→ MultiAgentExecutor
→ ResultAggregator
→ ReflectionLoop
→ AggregatedResponse
```

## Planner

`TaskPlanner` validates the objective, infers or accepts requested capabilities, removes duplicates, and emits dependency-ordered `TaskStep` records. Each step includes:

- a stable step ID;
- an objective scoped to that capability;
- required capabilities;
- dependency IDs;
- a safe execution hint such as `local`, `permission_gated`, or `local_with_text_fallback`.

The recovery baseline creates one step per requested or inferred capability. Multiple steps are ordered deterministically. Reflection is performed by the internal `ReflectionLoop` after aggregation rather than by inserting a second execution of the selected agent.

The bootstrap planner remains deterministic and rule-based so the backend is runnable without external model dependencies.

## Task graph

`TaskGraphBuilder` converts planner steps into `TaskNode` objects. Nodes track:

- dependencies;
- assigned agent;
- assigned model profile;
- assigned tool adapter;
- execution mode;
- execution status;
- result payload.

The graph rejects duplicate node IDs, unknown dependencies, and cycles, then computes a dependency-respecting execution order.

## Capability routing

`CapabilityRouter` selects a route for each node. A route includes:

- selected agent;
- selected local-first model profile;
- selected tool adapter;
- execution mode;
- candidate agents;
- human-approval signal;
- rationale.

Current routes are deterministic metadata. Risky capabilities such as coding, repository access, tooling, plugins, and self-evolve require approval. Route selection does not itself grant shell, network, package installation, GitHub mutation, or external communication rights.

## Execution and aggregation

`MultiAgentExecutor` executes each node exactly once per execution attempt, in dependency order. It records route metadata before execution, marks failures, and stores the successful result on the node.

`ResultAggregator` combines node outputs and exposes:

- node count;
- pipeline stages;
- route decisions;
- node status records;
- agent names and confidence values.

## Reflection

After aggregation, the orchestrator runs one internal metacognitive `ReflectionLoop`. It estimates confidence and produces a self-critique from execution signals. Reflection is an engineering quality-control operation; it does not execute external actions and does not imply biological consciousness or subjective experience.

## Recovery invariants

1. A node is executed exactly once per execution attempt.
2. Planner steps and graph nodes use one canonical schema.
3. Graph structure is validated before execution.
4. Risky routes remain approval-gated.
5. Reflection is performed once after aggregation.
6. Completed tasks and reflection outcomes are recorded in runtime memory.

## Remaining work

- configurable model, tool, and route scoring;
- safe parallel execution of independent graph branches;
- retry, timeout, cancellation, and resumable run state;
- durable graph and execution-trace persistence;
- streaming task events;
- human approval checkpoints inside long-running graphs;
- independent result verification for high-risk tasks.
