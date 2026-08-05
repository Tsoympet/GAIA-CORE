# GAIA Implementation Gap Register

## Purpose

This register is the authoritative bridge between the recovered May 2026 repository and the complete GAIA Cognitive Operating System discussed through July 2026.

A feature is not considered implemented merely because a route, class name, configuration entry, placeholder client, scaffold, or architecture document exists. A feature reaches `IMPLEMENTED` only when production code, permission boundaries, persistence, tests, observability, rollback behavior, and operator documentation exist.

## Status definitions

- `RECOVERED`: coherent foundation restored from merge corruption.
- `SCAFFOLDED`: interfaces or placeholders exist but the capability is not operational.
- `PARTIAL`: some real behavior exists, but major production requirements remain.
- `MISSING`: no usable implementation exists.
- `EXPERIMENTAL`: sandbox-only implementation; production actions are prohibited.
- `IMPLEMENTED`: complete, tested, governed, and documented.

## Current baseline

| Capability | Status | Current evidence | Required completion work |
|---|---|---|---|
| Deterministic planner and DAG | RECOVERED | Canonical `TaskStep`, validated graph, one node per capability | Durable runs, branch parallelism, streaming events, cancellation, retries |
| Capability router | RECOVERED | Agent/model/tool metadata and approval signal | Scored registry, health/cost/privacy constraints, provider failover |
| Agent execution | RECOVERED | One agent invocation per node | Sandboxed tool runtime, budgets, cancellation, retries, trace persistence |
| Result aggregation and reflection | RECOVERED | Structured response and internal reflection | Independent verification agents, evidence scoring, contradiction handling |
| Runtime event memory | PARTIAL | Append-only in-memory records | Durable persistence, project/session binding, encryption, migrations |
| Scoped memory | PARTIAL | Consent, scopes, index, export, reviewed deletion | Durable records, provenance, contradiction states, backup/restore |
| Workspace persistence | PARTIAL | SQLite workspace metadata | Full workspace graph, files, repositories, decisions, timelines and permissions |
| Model fabric | SCAFFOLDED | Registry, Ollama/local placeholders, guarded cloud fallback | Real inference clients, model health, capability benchmarks, resource routing |
| Security and permissions | PARTIAL | Permission manager, guards, kill switch and policy scaffolding | Unified policy engine, signed approvals, sandbox profiles, audit persistence |
| Voice | SCAFFOLDED | Typed profiles, STT/TTS adapters, routes and desktop placeholders | Real local STT/TTS, streaming audio, duplex sessions, interruption and consent |
| Self-model and metacognition | SCAFFOLDED | Confidence and critique primitives | Capability calibration, limitation tracking, contradiction and failure models |
| Dream Laboratory | SCAFFOLDED | Idle/dreaming modules and no-action guard | Isolated replay, simulation store, consolidation policy, hypothesis validation |
| Self-evolution | SCAFFOLDED | Agent/capability labels and policy description | GAIA Forge, immutable skill registry, evaluation and approval pipeline |
| Cognitive Kernel | PARTIAL | Unified `gaia.kernel` control plane with SQLite persistence, events, and resume | SSE/WebSocket streaming, desktop surfaces, backup/restore |
| Cognitive Continuity | MISSING | Basic sessions only | Signed checkpoints, restart recovery, model-switch continuity, stale-state checks |
| Memory Organism | MISSING | Separate memory primitives exist | Unified typed memory classes with provenance, promotion and retention rules |
| Evidence and Provenance Ledger | MISSING | Route artifacts and basic metadata only | Source hashes, confidence, validation states, lineage, contradictions and supersession |
| Living Project Intelligence | MISSING | Workspace metadata only | Project graph for requirements, decisions, files, repositories, risks and versions |
| Skill Registry | MISSING | No governed skill package format | Immutable versions, signatures, permissions, dependencies, tests and rollback |
| GAIA Forge | MISSING | No operational skill creation pipeline | Workflow discovery, candidate generation, sandbox evaluation and promotion review |
| Research Laboratory | MISSING | No campaign manager | Baselines, hypotheses, branches, budgets, experiment ledger and paper-to-code review |
| Tool runtime | MISSING | Tool names are routing metadata only | Typed adapters, sandboxing, dry-run, permissions, cancellation, audit and rollback |
| Computer use | MISSING | No production desktop/browser controller | Screen state, accessibility APIs, action confirmation, recovery and injection defense |
| Retrieval and deep research | SCAFFOLDED | Research agent placeholder | Source connectors, provenance, citation graph, freshness and contradiction checks |
| Multimodal vision | SCAFFOLDED | Agent and routing labels | Real local vision model, evidence storage, image/video pipelines and evaluation |
| Document intelligence | SCAFFOLDED | Document agent label/routes | PDF, office, spreadsheet parsers, structured extraction, citations and validation |
| Coding and repository intelligence | SCAFFOLDED | Deterministic capability agent | Real repository tools, isolated execution, test/CI analysis and patch workflow |
| CAD/CAE engineering integration | SCAFFOLDED | CAD/engineering labels | File adapters, geometry metadata, solver interfaces, simulation provenance |
| Robotics and physical AI | MISSING | Architecture discussion only | Simulation adapters, safety interlocks, deterministic controller and operator presence |
| Desktop mission-control application | SCAFFOLDED | React/Tauri shell and panels | Live backend integration, project/memory/task views, permissions and rollback UI |
| Packaging and updates | PARTIAL | Docker/deployment scaffolding | Windows/Linux installers, signed releases, migrations, backups and safe updater |
| Observability | PARTIAL | Response artifacts and basic logs | Persistent traces, metrics, resource use, security events and operator diagnostics |

## Mandatory implementation sequence

### R0 — Repository recovery

- Remove merge corruption and stale contracts.
- Establish compile, lint, strict typing and complete test gates.
- Publish a versioned clean baseline.

### R1 — Cognitive Kernel foundation

Implement:

- `gaia/kernel/goal_manager.py`
- `gaia/kernel/context_manager.py`
- `gaia/kernel/resource_budget.py`
- `gaia/kernel/policy_coordinator.py`
- `gaia/kernel/verification_coordinator.py`
- `gaia/kernel/interrupt_controller.py`
- typed kernel state and APIs

No external autonomy is enabled in R1.

### R2 — Cognitive Continuity

Implement:

- signed session checkpoints;
- task graph and repository-state snapshots;
- safe restart/resume;
- stale resource and permission validation;
- model-switch continuity;
- rollback to the last verified checkpoint.

### R3 — Memory Organism and Provenance Ledger

Implement durable working, episodic, semantic, procedural, project, correction, simulation, identity, timeline and evidence memories with explicit promotion rules.

### R4 — Living Project Intelligence

Implement project graphs connecting requirements, decisions, repositories, files, versions, risks, experiments, tests and unresolved questions.

### R5 — Tool Runtime and Computer Use

Implement permission-scoped tools with dry-run, sandbox, budgets, cancellation, logs and rollback. Browser and desktop control remain approval-gated.

### R6 — Skill Registry and GAIA Forge

Implement immutable signed skill packages, candidate generation, evaluation, adversarial testing, approval, promotion, deprecation and rollback.

### R7 — Research Laboratory

Implement reproducible research campaigns, paper ingestion, experiment branches, metric ledgers, budgets and independent validation.

### R8 — Voice and Multimodal Runtime

Replace placeholders with operational local-first STT/TTS, duplex voice sessions, interruption handling, vision/document pipelines and privacy controls.

### R9 — Desktop Mission Control

Connect the Tauri/React interface to live kernel, project, memory, agent, model, permission, research, Forge, dream and rollback services.

### R10 — Engineering and Physical-AI adapters

Add CAD/CAE, digital-twin, visual maintenance and simulation-only robotics adapters. Physical actuation remains prohibited until independent safety certification.

## Definition of done for every capability

Every implemented feature must include:

1. Typed interfaces and schemas.
2. A real implementation rather than a placeholder response.
3. Explicit permission and privacy behavior.
4. Persistent state where continuity is required.
5. Unit, integration, security and failure-path tests.
6. Structured logs and audit records.
7. Resource and timeout limits.
8. A rollback or safe-disable path.
9. Operator documentation and configuration.
10. CI enforcement.

## Prohibited shortcuts

- Counting a route or empty class as an implemented capability.
- Merging generated code without tests and review.
- Enabling unrestricted shell, network, GitHub or desktop access.
- Allowing experimental or dream outputs to modify production state.
- Depending on one model provider for GAIA identity or continuity.
- Storing sensitive project data in external services by default.
- Automatically promoting self-generated skills or code.

## Immediate work after R0

The first implementation PR after the recovery baseline will be **R1 Cognitive Kernel Foundation**. It will introduce the kernel state model, goal manager, context manager, resource budgets, verification coordination, interruption controls, API surfaces and tests while preserving the existing recovered orchestrator as a compatibility execution engine.
