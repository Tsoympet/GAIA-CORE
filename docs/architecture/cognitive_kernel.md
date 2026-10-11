# Cognitive Kernel (R1)

The Cognitive Kernel is the platform control plane for GAIA. It sits above the
recovered orchestrator and owns goal state, working context, resource budgets,
policy admission, verification, interruption, durable persistence, streaming
events, backup/restore, and desktop operator surfaces.

## Responsibilities

- admit or block goals through the shared security policy and kill switch;
- track goal lifecycle (`pending` → `active` → terminal states);
- bind bounded working context per goal;
- enforce resource budgets (steps, model/tool calls, wall time, memory writes);
- verify aggregated orchestration outputs before marking goals completed;
- honor cancellation and global interrupt latches without external autonomy;
- persist goals, contexts, budgets, and lifecycle events in local SQLite;
- resume interrupted goals through another verified kernel run;
- stream durable/live kernel events over SSE;
- backup, restore, delete, and purge durable kernel state under permissions;
- expose a desktop mission-control surface for goals, budgets, and events.

## Package layout

- `gaia/kernel/goal_manager.py` — goal registry and lifecycle
- `gaia/kernel/context_manager.py` — bounded working context
- `gaia/kernel/resource_budget.py` — budgets and consumption tracking
- `gaia/kernel/policy_coordinator.py` — security/permission admission
- `gaia/kernel/verification_coordinator.py` — post-run verification gates
- `gaia/kernel/interrupt_controller.py` — cancel/interrupt latches
- `gaia/kernel/store.py` — SQLite persistence, migrations, backup/restore/delete
- `gaia/kernel/events.py` — durable event log and bus fan-out
- `gaia/kernel/config.py` — validated `config/kernel.yaml` loading
- `gaia/kernel/kernel.py` — composition root, `run()`, and `resume()`

## Security

Kernel operator APIs require permissions:

- `kernel.read` — status, goals, events, tasks, resume/cancel
- `kernel.delete` — goal deletion including durable derivatives
- `kernel.backup` — backup creation
- `kernel.admin` — restore and purge

Risky kernel admin permissions require human-approved grants. Local durable CLI
runtimes receive approved local-operator grants; in-memory test runtimes receive
read-only grants by default.

## Runtime wiring

`GaiaRuntime.submit_task` routes every task through `CognitiveKernel.run`.
The recovered orchestrator remains the execution engine.

Default `create_runtime()` uses an in-memory kernel database for isolated tests.
CLI `serve` / `run` / `status` use `.gaia/kernel.sqlite3` for durable local state.

## Operator API

- `GET /kernel/status`
- `GET /kernel/goals`
- `GET /kernel/goals/{goal_id}`
- `DELETE /kernel/goals/{goal_id}`
- `POST /kernel/goals/{goal_id}/cancel`
- `POST /kernel/goals/{goal_id}/resume`
- `GET /kernel/interrupts`
- `GET /kernel/events`
- `GET /kernel/events/stream` (SSE)
- `POST /kernel/backup`
- `POST /kernel/restore`
- `POST /kernel/purge`
- `POST /kernel/tasks`

## Desktop

The Tauri/React shell includes a live **Cognitive Kernel** page with goal
submission, status metrics, resume/cancel/delete actions, backup, and SSE event
streaming via the Vite API proxy.

## Status

R1 Cognitive Kernel is **IMPLEMENTED** for the control-plane completion
standard: typed interfaces, runtime wiring, durable schema/migration,
backup/restore/deletion, permissions/audit, tests, API, desktop surface, and
validated configuration.
