# GAIA Development Roadmap

## Immediate Checklist

- Keep `pytest -q` green.
- Expand planner from a single-node graph to safe deterministic decomposition.
- Add per-node retries, cancellation, and execution history persistence.
- Add permission approval APIs before enabling risky tools.
- Add workspace persistence with SQLite local mode.
- Add Ollama health checks and deterministic local fallback behavior.
- Build Tauri panels around runtime status, task submission, graph inspection, memory, security, self-model, metacognition, and dreaming.

## Milestones

### M1 — Runnable Local Core

- FastAPI server starts.
- CLI accepts a task.
- Runtime creates a plan, graph, route, agent execution, aggregation, and memory log.
- Security policy can block unsafe objectives.

### M2 — Secure Tools

- Shell, Python, file, Git, browser, Docker, API, document, image, audio, and CAD tools are registries only until permission gates and sandboxes are in place.

### M3 — Persistent Workspaces

- Project config, linked repositories, workspace memory, artifacts, task history, logs, and model preferences are stored locally.

### M4 — Model Fabric

- Ollama, llama.cpp, vLLM, HuggingFace, OpenAI-compatible APIs, embeddings, and health checks share one local-first routing layer.

### M5 — Cognitive Simulation Layers

- Self-model, metacognition, consciousness simulation, affect simulation, and dreaming remain explicitly labeled as simulations and are audited as quality-control metadata.
