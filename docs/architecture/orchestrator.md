# Orchestrator

The orchestrator follows a planner/router/executor/aggregator pipeline inspired conceptually by HuggingGPT but implemented as typed GAIA primitives. A user task becomes a `TaskPlan`, the plan contains a DAG `TaskGraph`, the executor routes each node through the capability router, and the aggregator returns structured JSON.
