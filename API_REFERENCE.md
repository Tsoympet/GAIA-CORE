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

- `POST /chat`
- `GET /agents/status`
- `POST /memory`
- `GET /models`
- `POST /models`
- `GET /tools/status`
- `GET /workspaces/status`
- `POST /security/kill-switch`
- `DELETE /security/kill-switch`
- `GET /self-model/status`
- `GET /metacognition/status`
- `GET /dreaming/status`
- `GET /idle-cognition/status`

These routes establish stable API namespaces for the long-term GAIA platform while deeper implementations are added incrementally.
