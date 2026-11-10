# GAIA API Reference

The first runnable backend is FastAPI-based and starts with:

```bash
uvicorn gaia.server.app:app --reload
```

## Runtime

### `GET /health`

Returns runtime liveness and runtime id.

### `GET /runtime/status`

Returns configured agent names, capability names, and local-first status.

### `POST /tasks`

Runs the minimal GAIA pipeline: planner, task graph builder, capability router, executor, aggregator, and memory logging.

Request:

```json
{
  "task": "Plan a local-first assistant workflow",
  "session_id": null,
  "capabilities": [],
  "metadata": {}
}
```

### `POST /orchestrator/plan`

Creates a plan and routes nodes without executing them.

## Foundation Route Groups

These routes are served by the local runtime. Cloud model calls stay disabled. Ollama is used only when its daemon lists a ready model; otherwise chat and task answers come from the deterministic local client. That client does not download weights.

- `POST /chat` returns `message`, `model_id`, `provider`, `local_fallback`, and `deterministic`.
- `GET /agents/status` lists the live agent registry.
- `POST /memory` writes scoped memory. `POST /memory/recall` searches it for an owner.
- `GET /models` and `GET /models/health` report the local-first router. Cloud stays disabled.
- `GET /tools/status` reports tool permissions and does not execute tools.
- `GET /workspaces/status` and the workspace collection use the local SQLite store.
- `GET /security/status`, `GET /security/permissions`, `GET /security/audit`, and `POST /security/check` expose policy state. `POST /security/kill-switch` and `DELETE /security/kill-switch` share the runtime kill switch. Risky permissions still require human approval.
- `GET /self-model/status` returns the simulated self-model, including known limitations. It is not a consciousness claim.
- `POST /metacognition/review` runs the reflection loop. `GET /metacognition/status` reports the latest review.
- `POST /dreaming/cycle` and `POST /idle-cognition/cycle` run internal notes only. External actions are refused.
- `GET /kernel/status`, `POST /kernel/tasks`, and `POST /tasks` run the cognitive kernel and return a structured result.
- `GET /kernel/continuity` and `GET /organism/status` report the journal and memory organism when those database paths are set. `gaia serve` and `gaia run` default to `.gaia/continuity.sqlite3` and `.gaia/organism.sqlite3`.
- `GET /voice/status`, `POST /voice/synthesize`, and `POST /voice/transcribe` stay synthetic. `provider=synthetic-tone` returns a generated tone, not a cloned voice. Impersonation text is rejected.

Pass `--continuity-db` and `--organism-db` explicitly when those files should live somewhere else. Omit them only by pointing the flags at a path you do not want created; the CLI defaults create the local files.
