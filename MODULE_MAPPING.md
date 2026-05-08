# Reference-to-GAIA Module Mapping

| Reference concept | GAIA module | Adaptation |
|---|---|---|
| OpenJarvis agents | `src/gaia/agents/` | Typed `BaseAgent`, `AgentRegistry`, specialized agents, and future agent templates. |
| OpenJarvis tools/skills | `src/gaia/tools/`, `src/gaia/skills/`, future plugins | Capability-governed plugin system with audit and permission checks. |
| OpenJarvis memory/indexing | `src/gaia/memory/` | Local-first append-only manager now; scoped vector/symbolic stores later. |
| OpenJarvis model engines/Ollama | `src/gaia/models/` and local model fabric docs | Provider-neutral local-first model catalog and routing. |
| OpenJarvis CLI/server/desktop workflow | `src/gaia/cli.py`, `src/gaia/server/`, `desktop/` | Runnable FastAPI backend and Tauri/React mission-control shell. |
| OpenJarvis schedulers/channels | `src/gaia/autonomy/`, security guards | Disabled-by-default autonomy requiring permission and audit. |
| Microsoft JARVIS planner | `src/gaia/orchestrator/planner.py` | Typed task planning with future LLM-assisted decomposition. |
| Microsoft JARVIS model routing | `src/gaia/capabilities/capability_router.py` | Agent/model capability routing with local-first fallback. |
| Microsoft JARVIS executor | `src/gaia/orchestrator/executor.py` | DAG node execution via registered agents. |
| Microsoft JARVIS response synthesis | `src/gaia/orchestrator/aggregator.py` | Typed response aggregation, confidence, and artifacts. |
| HuggingGPT expert models | `src/gaia/capabilities/`, `src/gaia/models/` | Capability registry plus future model fabric for multimodal experts. |
| HuggingGPT multimodal flow | `src/gaia/voice/`, future vision/audio/document agents | Safe multimodal orchestration with local fallback. |
