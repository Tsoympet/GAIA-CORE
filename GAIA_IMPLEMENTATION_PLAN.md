# GAIA Implementation Plan

## Phase 1 — Repository Cleanup and Runnable Backend

Goals:
- Fix package metadata and test bootstrap.
- Establish one coherent runtime composition root.
- Provide FastAPI health, runtime status, planning, and task submission endpoints.
- Add pytest coverage for runtime startup, planning, routing, execution, memory, security, self-model, metacognition, and dreaming guard.

Deliverables:
- Valid `pyproject.toml`.
- `GaiaRuntime.submit_task()`.
- `/tasks` endpoint returning structured responses.
- Basic deterministic local agent.

Exit Criteria:
- `pytest -q` passes.
- `create_app()` starts without crashing.
- A user task can move through planner → graph → router → executor → aggregator.

## Phase 2 — OpenJarvis-Derived Local Assistant Runtime

Goals:
- Add local model fabric with Ollama first, then llama.cpp/vLLM/HuggingFace adapters.
- Add registry-based tools and skills.
- Add runtime traces and event stream.
- Add local memory retrieval/context injection.

Deliverables:
- `src/gaia/models/model_fabric.py`.
- `src/gaia/tools/` and `src/gaia/skills/` registries.
- Trace records for model calls, tool calls, routes, memory lookups, and agent output.

Exit Criteria:
- Local Ollama generation can be selected through the same capability route interface.
- Tool calls are permission-gated and audited.

## Phase 3 — JARVIS-Style Planner / Router / Executor

Goals:
- Upgrade planner from one-step DAG to multi-node decomposition.
- Add capability and model selection scoring.
- Add executor pipeline with dependencies, parallel-safe nodes, retries, and timeouts.
- Add response aggregation with source and artifact tracking.

Deliverables:
- `TaskGraph` dependency resolver.
- `CapabilityRouter` scoring model.
- `ResultAggregator` with per-node provenance.

Exit Criteria:
- Multi-step tasks produce inspectable DAGs and execute in dependency order.

## Phase 4 — Memory and Workspaces

Goals:
- Add workspace model and local persistence.
- Add scoped memory: user, project, workspace, runtime, and ephemeral.
- Add vector/symbolic retrieval backends.

Deliverables:
- `src/gaia/workspaces/`.
- SQLite local store.
- Optional FAISS/Chroma/Qdrant adapters.

Exit Criteria:
- Tasks can write/read workspace memories with tests and source attribution.

## Phase 5 — Desktop UI

Goals:
- Turn the existing Tauri/React skeleton into the primary GAIA operating surface.
- Add task console, plan graph viewer, memory viewer, security review panel, agent status, and settings.

Deliverables:
- Desktop API client.
- Runtime status and task submission UI.
- Permission approval UI.

Exit Criteria:
- A local user can submit tasks and inspect plans/results from desktop.

## Phase 6 — Self-Model and Metacognition

Goals:
- Track known capabilities, limitations, uncertainty, confidence, and task self-evaluation.
- Keep language explicit: simulated self-model, introspection layer, metacognitive monitor.

Deliverables:
- Capability self-map.
- Limitation registry.
- Reflection reports attached to task results.

Exit Criteria:
- Every non-trivial task can produce confidence and critique metadata without consciousness claims.

## Phase 7 — Idle Cognition / Dreaming Simulation

Goals:
- Add safe idle cycles for memory consolidation, problem replay, synthetic scenario generation, and goal rehearsal.
- Guarantee no external actions from idle cognition.

Deliverables:
- Idle scheduler.
- No-action guard.
- Internal notes store.

Exit Criteria:
- Tests prove external-action operations are blocked.

## Phase 8 — Security Hardening

Goals:
- Mature policy enforcement, audit logs, human approval, sandboxing, and kill switch.
- Gate shell, deletion, network, GitHub push, package install, API-key use, code execution, scheduled autonomy, and external communication.

Deliverables:
- Policy configuration loader.
- Approval workflow.
- Sandbox adapters.
- Signed/append-only audit log option.

Exit Criteria:
- Risky actions cannot run without explicit human-approved policy decisions.

## Phase 9 — Plugins and External Tools

Goals:
- Add plugin manifest format, registry, installation checks, and permissions.
- Support external tools through sandboxed adapters.

Deliverables:
- `src/gaia/plugins/`.
- Plugin manifest validation.
- Tool capability declarations.

Exit Criteria:
- Plugins can be discovered and disabled without changing core runtime code.

## Phase 10 — Production Deployment

Goals:
- Add Docker, Compose, systemd, deployment docs, observability, metrics, and CI.
- Support local desktop mode and server mode.

Deliverables:
- `deployment/` directory.
- Dockerfile and Compose profile.
- OpenTelemetry/Prometheus hooks.

Exit Criteria:
- GAIA can run repeatably in local, desktop, and container environments.
