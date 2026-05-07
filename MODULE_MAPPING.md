# Reference System to GAIA Module Mapping

| Reference concept | GAIA module | Adaptation |
| --- | --- | --- |
| OpenJarvis core runtime / engine boundary | `src/gaia/core/runtime.py` and future `src/gaia/models/model_fabric.py` | Use local-first runtime composition and model backend abstractions. |
| OpenJarvis sessions | `src/gaia/core/session.py` | Track user/workspace execution context. |
| OpenJarvis agent system | `src/gaia/agents/` | Native async `BaseAgent`, deterministic bootstrap agents, future tool-using/ReAct/code agents. |
| OpenJarvis registry pattern | `src/gaia/agents/agent_registry.py`, `src/gaia/capabilities/capability_registry.py` | Typed registries for discovery without copying implementation. |
| OpenJarvis tool/skill system | Future `src/gaia/tools/` and `src/gaia/skills/` | Permission-gated tools and installable skills. |
| OpenJarvis memory concepts | `src/gaia/memory/` | Start with append-only memory manager; extend to scoped/vector/symbolic stores. |
| OpenJarvis Ollama/local inference support | `src/gaia/models/` | Local-first model fabric with Ollama, llama.cpp, vLLM, HF, optional cloud fallback. |
| OpenJarvis FastAPI server patterns | `src/gaia/server/app.py` | Health, status, planning, task submission endpoints. |
| OpenJarvis desktop/server structure | `desktop/` and `src/gaia/server/` | Tauri/React desktop consuming FastAPI backend. |
| OpenJarvis sandbox/security | `src/gaia/security/` | Deny-by-default permission manager, audit log, kill switch, future sandbox. |
| OpenJarvis trace-driven learning | Future `src/gaia/telemetry/` and `src/gaia/metacognition/` | Record execution traces and feed reflective review. |
| Microsoft JARVIS task planning | `src/gaia/orchestrator/planner.py` | Typed planner output rather than prompt-only parsing. |
| Microsoft JARVIS task graph decomposition | `src/gaia/orchestrator/task_graph.py` | DAG nodes with dependencies and assigned agents. |
| Microsoft JARVIS model selection | `src/gaia/capabilities/capability_router.py` | Capability router selects agents now; models/tools/plugins later. |
| Microsoft JARVIS executor | `src/gaia/orchestrator/executor.py` | Multi-agent executor runs DAG nodes in dependency order. |
| Microsoft JARVIS response generation | `src/gaia/orchestrator/aggregator.py` | Structured aggregation with confidence and provenance. |
| HuggingGPT expert model routing | Future `src/gaia/models/` + `src/gaia/capabilities/` | Route multimodal tasks to local/cloud expert models under permissions. |
| GAIA self-model vision | `src/gaia/self_model/` | Simulated self-model, capability map, limitation tracking. |
| GAIA metacognition vision | `src/gaia/metacognition/` | Confidence estimator, self-critique, reflection loop. |
| GAIA dreaming / idle cognition vision | `src/gaia/dreaming/` | Safe internal-only analysis, consolidation, replay, synthetic scenarios, goal rehearsal. |

## First Runnable Backend Mapping

| Required output | GAIA implementation |
| --- | --- |
| OpenJarvis study notes | `ARCHITECTURE_COMPARISON.md` study-note sections. |
| Microsoft JARVIS study notes | `ARCHITECTURE_COMPARISON.md` study-note sections. |
| Architecture comparison | `ARCHITECTURE_COMPARISON.md`. |
| Module mapping | `MODULE_MAPPING.md`. |
| Implementation roadmap | `GAIA_IMPLEMENTATION_PLAN.md` and `DEVELOPMENT_ROADMAP.md`. |
| Backend implementation | `src/gaia/core/runtime.py`, `src/gaia/server/app.py`, `src/gaia/orchestrator/`, `src/gaia/agents/`, `src/gaia/security/`. |
| Initial tests | `tests/` unit and integration tests. |
| Next-step checklist | `DEVELOPMENT_ROADMAP.md`. |
