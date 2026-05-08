# Orchestrator

The GAIA orchestrator follows a local-first planner/router/executor/aggregator
pipeline inspired conceptually by HuggingGPT, but implemented as original typed
GAIA primitives rather than copied Microsoft JARVIS code.
The GAIA orchestrator is a local-first planner/router/executor/aggregator pipeline inspired conceptually by Microsoft JARVIS / HuggingGPT, but implemented as original typed GAIA primitives.

## Phase 3 Pipeline

```text
User request
→ TaskPlanner
→ TaskGraph
→ structured PlanStep list
→ TaskGraph DAG
→ CapabilityRouter
→ MultiAgentExecutor
→ ResultAggregator
→ ReflectionLoop
→ AggregatedResponse
```

## Planner

`TaskPlanner` validates the objective, infers or accepts requested capabilities,
and emits structured `TaskStep` records. Each step includes:

- a stable step id
- an objective scoped to that step
- required capabilities
- dependency ids
- a safe execution hint such as `local`, `permission_gated`, or
  `local_with_text_fallback`

The bootstrap planner remains deterministic and rule-based so the backend is
runnable without external model dependencies.

## Task Graph

`TaskGraphBuilder` converts planner steps into `TaskNode` objects. Nodes track:

- dependencies
- assigned agent
- assigned model profile
- assigned tool adapter
- execution mode
- execution status
- result payload

The graph validates dependency references and computes a dependency-respecting
execution order.

## Capability Routing

`CapabilityRouter` selects a route for each node. A route includes:

- selected agent
- selected local-first model profile
- selected tool adapter
- execution mode
- candidate agents
- human approval signal
- rationale

Current routes are heuristic and safe by default. They do not grant shell,
network, package installation, GitHub push, or external communication rights.

## Execution and Aggregation

`MultiAgentExecutor` executes nodes in graph order, updates node state, and stores
agent results. `ResultAggregator` combines node outputs and includes route and
node execution metadata in response artifacts.

## Reflection

After aggregation, the orchestrator runs the metacognitive `ReflectionLoop` to
estimate confidence and produce a self-critique. This is simulated engineering
self-review only; GAIA does not claim consciousness or subjective experience.
→ final structured response
```

## Current Behavior

- The planner emits deterministic `PlanStep` objects with IDs, objectives, required capabilities, dependencies, and rationale.
- If the caller supplies explicit capabilities, GAIA creates one focused routed node for compatibility with direct API callers.
- If capabilities are inferred, GAIA creates a three-step bootstrap DAG:
  1. planning step
  2. primary execution step
  3. reflection step
- The task graph stores node dependencies, execution status, assigned agent, and result payloads.
- The capability router selects an agent, local-first model family, optional safe internal tool adapter, and execution mode.
- The executor runs nodes in dependency order and stores node results.
- The aggregator combines node outputs and route artifacts.
- The reflection loop estimates confidence/uncertainty and adds a metacognitive report to response artifacts.

## Safety Boundaries

The Phase 3 pipeline does not perform external actions by itself. Tool names such as `repo_inspector`, `memory_search`, and `research_summarizer` are routing metadata for safe future adapters; they are not network, shell, package-install, or file-deletion execution paths.
