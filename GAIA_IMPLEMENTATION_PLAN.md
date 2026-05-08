# GAIA Implementation Plan

## Phase 1: Repository cleanup and runnable backend
- Keep FastAPI app importable and covered by tests.
- Maintain typed runtime composition and `/tasks` endpoint.
- Add CI checks, linting, and baseline packaging.

## Phase 2: OpenJarvis-derived runtime foundation
- Expand CLI/server/desktop lifecycle.
- Add skills/tools registry and local connector ingestion.
- Add Ollama and local model health checks.

## Phase 3: JARVIS-style planner/router/executor
- Status: initial implementation added.
- Evolve single-node plans into multi-node DAG decomposition.
- Add model/capability scoring and execution traces.
- Add response synthesis over artifacts.
- Current foundation supports structured planner steps, dependency-backed task
  graph nodes, agent/model/tool/execution-mode routing hints, aggregation, and
  a metacognitive reflection pass in the runtime response artifacts.
- Next refinements: replace heuristic decomposition with configurable planners,
  add route scoring weights, persist execution traces, and introduce streaming
  task events.

## Phase 4: Memory and workspace system
- Add scoped workspace stores, timeline memory, symbolic memory, and vector backends.
- Add memory consent, retention, export, and deletion review.

## Phase 5: Desktop UI
- Build mission-control navigation for tasks, agents, graphs, memory, models, security, voice, and settings.
- Add streaming status and human override controls.

## Phase 6: Self-model and metacognition
- Implement simulated self-model, capability maps, limitation registry, confidence, uncertainty, and reflective review.
- Keep terminology explicit: engineering simulation, not biological consciousness.

## Phase 7: Idle cognition / dreaming simulation
- Add no-action idle scheduler, memory consolidation, session summarization, replay, synthetic scenarios, and dream journal.
- Enforce no external actions, no deletion, no package install, no GitHub push, and no external communication.

## Phase 8: Voice system
- Integrate Piper/Coqui/XTTS/Bark/OpenVoice only after license and consent review.
- Add Whisper/faster-whisper STT, wake word, microphone/speaker sessions, voice logs, and text fallback.

## Phase 9: Security hardening
- Enforce permission manager, policy engine, command/file/network guards, secrets manager, audit log, rollback, self-modification guard, and kill switch.

## Phase 10: Plugin ecosystem
- Define plugin manifests, signatures, capability declarations, sandbox policies, and marketplace governance.

## Phase 11: Production deployment
- Add Docker images, worker services, reverse proxy, systemd units, observability, backups, and release automation.
