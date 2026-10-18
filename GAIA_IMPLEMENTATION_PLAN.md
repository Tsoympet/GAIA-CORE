# GAIA Implementation Plan

GAIA is developed as an original, local-first Cognitive Operating System. Language models are replaceable reasoning components; the permanent platform consists of the cognitive kernel, memory, project intelligence, permissions, tools, evidence, and controlled learning systems.

No new autonomous capability may bypass the recovery, validation, permission, or human-approval gates defined below.

## R0 — Repository recovery and clean baseline

Status: validated on `agent/recover-orchestrator-baseline` (merged baseline).

Required outcomes:

- remove duplicate merge fragments and conflicting implementations;
- restore one canonical orchestration contract;
- guarantee one agent invocation per graph node;
- normalize tests and documentation;
- repair deletion, provenance, and audit invariants;
- add CI for compile, lint, type, and test checks;
- issue a versioned clean baseline before feature expansion.

## R1 — Cognitive Kernel

Status: **IMPLEMENTED** on `cursor/r1-cognitive-kernel-05ea`.

Build the stable platform center responsible for:

- goals and task state;
- context and resource management;
- planning and task graphs;
- model, agent, and tool routing;
- verification and uncertainty;
- permissions and policy enforcement;
- cancellation, interruption, and safe recovery.

Delivered: typed control plane, SQLite persistence/migrations, backup/restore/
delete/purge, SSE event streaming, resumable interrupts, permission-gated
operator APIs, validated config, desktop kernel mission-control surface, and
regression tests, preserving the recovered orchestrator as the execution engine.

## R2 — Cognitive Continuity

Status: partial. Opt-in local SQLite journal on top of `KernelStore`.
`KernelStore` remains the live goal, context, and budget store.

Delivered: schema v1, validated task states, hash-linked checkpoints, recovery
of in-flight work, non-reusable approvals, redaction, branches, resume, audit
export, and operator routes. See `docs/architecture/cognitive_continuity.md`.

Still open: repository/process snapshots. A desktop Continuity page can
inspect, publish, verify, and follow a process-local event stream. Explicit
session ids, user id, workspace id, creation time, and redacted metadata
are restored from the journal. Approval grants are not.
Optional AES-GCM field encryption seals secret JSON when a data key is set.
Checkpoints are tamper-evident, not a cryptographic ledger.

## R3 — Memory Organism and Provenance Ledger

Status: partial. Opt-in local SQLite evidence ledger and memory organism.

Delivered: schema v1, evidence hash chain with body purge, promotion and
refusal rules, corrections, deletion, hybrid local retrieval, kernel outcome
redaction, `/organism` routes, and `gaia organism`. See
`docs/architecture/memory_organism.md`.

Also delivered: published continuity checkpoints are cited in the evidence
ledger by digest when both stores are configured. The payload stays in the
continuity journal. Organism tables and evidence tables can each be forced
back to an empty version 0 without dropping the other group.

Also delivered: optional AES-GCM field encryption for evidence bodies and
memory text. A missing or wrong key fails closed.

Identity, timeline, and preference categories are present. Timeline records
require `event_at`. Identity and preference approval do not become factual
knowledge. A new preference supersedes only a preference it cites. Hybrid
retrieval combines BM25 with character n-grams and a hashed derived index.
A desktop Organism page can inspect status, record evidence, search, and
promote a cited candidate. Neural embeddings and calibrated confidence
remain open. The hash chain is tamper-evident, not cryptographic
immutability. Phase 4 scoped memory stays in process memory.

The light client is deferred until these local platform gaps are closed.

The organism keeps these classes separate: working, episodic, semantic,
procedural, project, correction, user-preference, simulation, identity, and
timeline. Preference and identity stay non-factual.

Still required: provenance, confidence, validation state, retention policy,
contradictions, dependencies, and derived-record lineage on every important
record. Deletion must include derived summaries and indexes.

## R4 — Living Project Intelligence

Represent each project as a versioned knowledge structure containing objectives, requirements, files, repositories, decisions, dependencies, risks, tests, evidence, unresolved questions, and future actions.

## R5 — Skill Registry and GAIA Forge

Create immutable, signed, versioned skills with compatibility, permissions, evaluations, promotion states, and rollback targets.

Forge may observe repeated workflows, generate candidate skills, test them in isolation, compare performance, and request approval. It may not promote its own output or change safety policy.

## R6 — Research Laboratory

Implement controlled research campaigns with:

- frozen baselines;
- hypotheses;
- isolated experiment branches;
- paper ingestion and algorithm extraction;
- paper-to-code translation;
- reproducibility checks;
- metric and evidence ledgers;
- compute and time budgets;
- independent review;
- approval-gated promotion.

## R7 — Voice and multimodal runtime

Complete the unique synthetic GAIA voice, local speech recognition, wake word, interruption handling, full-duplex session design, vision, document, image, and audio routing. Retain text fallback and explicit consent for voice export or biometric processing.

## R8 — Desktop mission-control interface

Build the production Tauri/React workstation for tasks, graphs, projects, memory, evidence, models, agents, skills, research campaigns, dreaming, voice, permissions, security, resources, audit, and rollback.

## R9 — Secure tools and computer use

Enable files, terminal, Python, browser, Git, GitHub, Docker, documents, spreadsheets, media, APIs, and CAD/CAE only through declared capabilities, sandboxes, resource limits, audit logs, dry-run support, confirmation gates, and rollback.

## R10 — Dream Laboratory and controlled self-improvement

Idle cognition may consolidate memory, replay failures, test alternatives, identify contradictions, and generate hypotheses inside an isolated no-action environment. Simulation output remains untrusted until independently validated.

## R11 — Physical-AI simulation adapters

Add robotics, world-model, digital-twin, and visual-maintenance adapters in simulation only. Physical actuation remains prohibited until deterministic interlocks, emergency stop, operator presence, and independent safety validation exist.

## R12 — Production deployment and plugin ecosystem

Add signed plugins, package governance, migration tools, backup and restore, observability, Docker images, system services, release automation, and supported Windows/Linux installers.

## Non-negotiable rules

- local-first and offline-capable by default;
- human override always available;
- no hidden goals or concealed actions;
- no automatic permission expansion;
- no automatic production merge or self-promotion;
- no cloud transfer of private project data without approval;
- no simulated result represented as fact;
- no deletion that leaves searchable derived data;
- no external communication, installation, GitHub mutation, or destructive file action without policy approval;
- no claim of biological consciousness or legal/moral independence.
