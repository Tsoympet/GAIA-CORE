# GAIA Capability Implementation Register

This register is the authoritative engineering backlog for turning GAIA from an unfinished foundation into the local-first Cognitive Operating System defined by the project.

A feature is **not implemented** merely because a document, route stub, class name, UI panel, provider placeholder, or deterministic fallback exists.

## Completion standard

A capability may be marked `IMPLEMENTED` only when all applicable requirements are satisfied:

1. production-oriented source code exists behind typed public interfaces;
2. the capability is wired into the canonical runtime composition root;
3. durable state has a schema, migration, backup, restore, and deletion path;
4. permissions, threat boundaries, audit events, and rollback are defined;
5. unit, integration, failure, security, and regression tests pass;
6. an API and desktop surface exist when operator interaction is required;
7. configuration is validated and secrets are not embedded in code;
8. model, dataset, library, and transitive licenses are recorded;
9. placeholder output is not presented as a completed operation;
10. documentation describes actual behavior rather than planned behavior.

Allowed states:

- `RECOVERY`: existing code is being repaired and validated;
- `PARTIAL`: useful working code exists but completion criteria are unmet;
- `SCAFFOLD`: interfaces or placeholders exist without complete operation;
- `MISSING`: no coherent implementation exists;
- `IMPLEMENTED`: all completion criteria are met;
- `DEFERRED`: intentionally postponed with a recorded reason;
- `REJECTED`: excluded by architecture or safety policy.

## Platform capabilities

| Capability | Current state | Existing foundation | Required implementation work |
|---|---|---|---|
| Repository integrity and CI | RECOVERY | Recovery PR, compile/lint/type/test workflow | Complete repository scan, obtain green validation, release clean baseline |
| Cognitive Kernel | IMPLEMENTED | Typed kernel package, runtime wiring, `/kernel` API, SQLite persistence/migrations, SSE events, resume, backup/restore/delete/purge, permissions, desktop kernel page, config, regression tests | Later platform work may extend streaming transport (WebSocket) and richer desktop graph views without reopening R1 |
| Cognitive Continuity | PARTIAL | Opt-in SQLite journal on top of KernelStore: task state machine, hash-linked checkpoints, crash recovery, process-local approvals, redaction, field encryption, restored session workspace and redacted metadata, desktop journal page for status, publish, verify, and task runs | Streaming continuity events, repository/process snapshots, cryptographic immutability |
| Task planning and DAG execution | PARTIAL | Deterministic planner, graph, router, executor, aggregator | Real decomposition, branch scheduling, retries, timeouts, cancellation, persistent runs, streaming events, approval nodes |
| Agent runtime | PARTIAL | Registry and deterministic capability agents | Typed specialist implementations, model/tool bindings, budgets, isolation, verifier agents, lifecycle and telemetry |
| Model Fabric | PARTIAL | Catalog, registry, Ollama adapter, local placeholder, disabled cloud fallback | llama.cpp, vLLM, Transformers, ONNX adapters, health probes, hardware routing, privacy classes, cost accounting, failover |
| Working memory | PARTIAL | Runtime event memory, scoped in-memory records, and organism working memories with `valid_until` | Kernel-bound limits, compression, trace linkage, encryption |
| Episodic memory | PARTIAL | Durable episodic records bound to evidence ids, owner, and optional project. Checkpoint citations are evidence digests, not episodic copies of the payload. Local hybrid retrieval ranks them with BM25 and character n-grams | Neural embeddings and calibrated confidence |
| Semantic memory | PARTIAL | In-memory Phase 4 vector index plus organism promotion to approved semantic memory. Organism search uses a durable hashed n-gram index, not neural embeddings | Durable neural embeddings, calibrated confidence, model/version metadata |
| Procedural memory | PARTIAL | Organism procedural candidates with the same promotion rules as semantic memory | Skill Registry versions, execution evidence, rollback of procedures |
| Correction memory | PARTIAL | Append-only correction memories; original content and hash stay unchanged | Regression linkage and automatic revalidation of approved dependents |
| Identity memory | PARTIAL | Organism identity candidates cite an observation, survive validation, and replace an older approved identity by contradiction. Approval does not set approved knowledge or change policy | Capability and limitation state, and calibrated confidence |
| Preference memory | PARTIAL | Organism preference candidates cite an observation. Approval does not set approved knowledge or change policy. A later approved preference contradicts only a cited preference for the same owner. Default hybrid search still hides preference unless opted in | Calibrated confidence |
| Simulation memory | PARTIAL | Organism simulation category that cannot be promoted into factual knowledge | Expiry policies beyond `valid_until`, isolated dream-lab store |
| Provenance and Evidence Ledger | PARTIAL | Insert-only SQLite headers, content hashes, purge receipts, chain verification, continuity checkpoint digest citations | Signatures, encryption, cryptographic immutability |
| Living Project Intelligence | MISSING | SQLite workspace metadata | Requirements graph, repository/file graph, decisions, risks, versions, tests, evidence, timelines and project APIs |
| Security policy engine | PARTIAL | Objective policy, permissions, guards, audit log, shared kill switch | Scoped grants, expiry, approval records, sandbox policies, policy persistence, event correlation, red-team tests |
| Tool Runtime | MISSING | Tool route stubs and routing metadata | Signed manifests, schemas, sandbox runner, quotas, dry-run, cancellation, audit, rollback and tool registry |
| File and terminal tools | MISSING | Functional guards only | Sandboxed implementations, workspace mounts, command allowlists, output capture and rollback |
| Browser and computer use | MISSING | None | Browser adapter, desktop accessibility layer, prompt-injection defense, confirmation gates and replay logs |
| Git and GitHub tools | MISSING | None in local runtime | Read/write adapters, branch policy, signed commits, PR workflow, approval and rollback |
| Document and spreadsheet tools | MISSING | Agent names and route placeholders | Parsers, renderers, structured editing, validation and artifact provenance |
| CAD/CAE integration | MISSING | CAD agent name only | AegisCAD adapters, geometry/artifact contracts, simulation jobs, result verification and project linkage |
| Voice identity | PARTIAL | Synthetic profile, TTS/STT interfaces, safety filters | Real local providers, consent records, encrypted profile storage, quality evaluation and export controls |
| Realtime voice interaction | SCAFFOLD | Microphone, speaker, wake-word and session placeholders | Full-duplex streaming, interruption, VAD, cancellation, local fallback and privacy controls |
| Vision and multimodal routing | SCAFFOLD | Agent names and provider-neutral concepts | Image/video model adapters, evidence capture, OCR fallback, local routing and evaluation |
| Self-model | SCAFFOLD | Typed simulation components | Kernel capability map, limitation registry, calibration evidence, versioned approved state |
| Metacognition | PARTIAL | Reflection loop and scaffold modules | Independent verification, contradiction detection, confidence calibration, failure taxonomy and benchmarks |
| Dream Laboratory | SCAFFOLD | No-action guard and idle-cycle components | Isolated simulator, scheduler, untrusted memory, resource budgets, validation and promotion workflow |
| Skill Registry | MISSING | None | Immutable signed versions, manifests, compatibility, permissions, evaluation history, promotion and rollback |
| GAIA Forge | MISSING | Self-evolve concept only | Workflow discovery, candidate generation, sandbox tests, adversarial evaluation, approval-gated promotion |
| Research Laboratory | MISSING | Weekly external research process only | Campaign manager, frozen baselines, hypotheses, branches, budgets, paper-to-code, reproduction and evidence packages |
| Automated science | MISSING | None | Dataset and experiment governance, statistical checks, reproducibility, critic and human review |
| Desktop mission control | SCAFFOLD | Tauri/React shell with live kernel, continuity journal, organism, and voice panels | Complete navigation, runtime streaming, task graph, projects, Phase 4 memory, skills, research, security and rollback |
| Observability | MISSING | Basic logging | Structured event schema, OpenTelemetry, metrics, traces, dashboards, privacy controls and retention |
| Plugin ecosystem | MISSING | None | Signed manifests, capability declarations, dependency isolation, license checks and governance |
| Deployment and installers | SCAFFOLD | Docker, Compose, NGINX and systemd placeholders | Reproducible images, migrations, health checks, Windows/Linux installers, update and rollback channels |
| Backup, restore and migration | PARTIAL | SQLite workspace, continuity, organism, and evidence files can be copied. Continuity, organism, and evidence each have a forced downgrade to an empty version 0. Organism and evidence downgrades do not drop each other's tables | Encrypted backups, selective restore of individual memories, and disaster-recovery tests |
| Robotics and physical AI | DEFERRED | None | Simulation adapters first; no actuation before deterministic interlocks, emergency stop and independent safety validation |

## Implementation order after Recovery R0

1. `R1 Cognitive Kernel`
2. `R2 Cognitive Continuity`
3. `R3 Memory Organism and Evidence Ledger`
4. `R4 Living Project Intelligence`
5. `R5 Skill Registry and GAIA Forge`
6. `R6 Research Laboratory`
7. `R7 Model Fabric, voice and multimodal runtime`
8. `R8 Desktop mission control`
9. `R9 Secure Tool Runtime and computer use`
10. `R10 Dream Laboratory and controlled improvement`
11. `R11 Physical-AI simulation adapters`
12. `R12 Production deployment, plugins and installers`

## Mandatory implementation rule

Future work must not close a capability item by adding only placeholders, fake provider results, static status messages, empty UI panels, or documentation. Partial delivery must remain labelled `PARTIAL` or `SCAFFOLD` until the completion standard is met.
