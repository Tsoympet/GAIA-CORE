# Cognitive Kernel (R1)

The Cognitive Kernel is the platform control plane for GAIA. It sits above the
recovered orchestrator and owns goal state, working context, resource budgets,
policy admission, verification, interruption, durable persistence, and run events.

## Responsibilities

- admit or block goals through the shared security policy and kill switch;
- track goal lifecycle (`pending` → `active` → terminal states);
- bind bounded working context per goal;
- enforce resource budgets (steps, model/tool calls, wall time, memory writes);
- verify aggregated orchestration outputs before marking goals completed;
- honor cancellation and global interrupt latches without external autonomy;
- persist goals, contexts, budgets, and lifecycle events in local SQLite;
- resume interrupted goals through another verified kernel run;
- emit durable kernel events and fan them out on the runtime `EventBus`.

## Package layout

- `gaia/kernel/goal_manager.py` — goal registry and lifecycle
- `gaia/kernel/context_manager.py` — bounded working context
- `gaia/kernel/resource_budget.py` — budgets and consumption tracking
- `gaia/kernel/policy_coordinator.py` — security/permission admission
- `gaia/kernel/verification_coordinator.py` — post-run verification gates
- `gaia/kernel/interrupt_controller.py` — cancel/interrupt latches
- `gaia/kernel/store.py` — SQLite persistence and schema migrations
- `gaia/kernel/events.py` — durable event log and bus fan-out
- `gaia/kernel/kernel.py` — composition root, `run()`, and `resume()`

## Runtime wiring

`GaiaRuntime.submit_task` routes every task through `CognitiveKernel.run`.
The recovered orchestrator remains the execution engine; the kernel does not
replace planning, routing, or agent execution.

Default `create_runtime()` uses an in-memory kernel database for isolated tests.
CLI `serve` / `run` / `status` use `.gaia/kernel.sqlite3` for durable local state.

## Operator API

- `GET /kernel/status`
- `GET /kernel/goals`
- `GET /kernel/goals/{goal_id}`
- `POST /kernel/goals/{goal_id}/cancel`
- `POST /kernel/goals/{goal_id}/resume`
- `GET /kernel/interrupts`
- `GET /kernel/events`
- `POST /kernel/tasks`

## Current state

R1 is **partially deepened**: durable SQLite persistence (schema v1), event log,
resume for interrupted goals, and API surfaces are implemented and tested.

Still required before Cognitive Kernel can be marked `IMPLEMENTED`:

- streaming SSE/WebSocket run events for desktop mission control;
- richer failure/security regression matrix;
- desktop panels for goals, budgets, and event timelines;
- backup/restore of the kernel database as part of platform DR.
