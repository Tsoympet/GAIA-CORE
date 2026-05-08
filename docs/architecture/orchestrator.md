# Orchestrator

The GAIA orchestrator is a local-first planner/router/executor/aggregator pipeline inspired conceptually by Microsoft JARVIS / HuggingGPT, but implemented as original typed GAIA primitives.

## Phase 3 Pipeline

```text
User request
→ TaskPlanner
→ structured PlanStep list
→ TaskGraph DAG
→ CapabilityRouter
→ MultiAgentExecutor
→ ResultAggregator
→ ReflectionLoop
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
