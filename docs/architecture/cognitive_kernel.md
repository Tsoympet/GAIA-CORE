# Cognitive Kernel (R1)

The Cognitive Kernel is the platform control plane for GAIA. It sits above the
recovered orchestrator and owns goal state, working context, resource budgets,
policy admission, verification, and interruption.

## Responsibilities

- admit or block goals through the shared security policy and kill switch;
- track goal lifecycle (`pending` → `active` → terminal states);
- bind bounded working context per goal;
- enforce resource budgets (steps, model/tool calls, wall time, memory writes);
- verify aggregated orchestration outputs before marking goals completed;
- honor cancellation and global interrupt latches without external autonomy.

## Package layout

- `gaia/kernel/goal_manager.py` — goal registry and lifecycle
- `gaia/kernel/context_manager.py` — bounded working context
- `gaia/kernel/resource_budget.py` — budgets and consumption tracking
- `gaia/kernel/policy_coordinator.py` — security/permission admission
- `gaia/kernel/verification_coordinator.py` — post-run verification gates
- `gaia/kernel/interrupt_controller.py` — cancel/interrupt latches
- `gaia/kernel/kernel.py` — composition root and `run()` API

## Runtime wiring

`GaiaRuntime.submit_task` routes every task through `CognitiveKernel.run`.
The recovered orchestrator remains the execution engine; the kernel does not
replace planning, routing, or agent execution.

## Operator API

- `GET /kernel/status`
- `GET /kernel/goals`
- `GET /kernel/goals/{goal_id}`
- `POST /kernel/goals/{goal_id}/cancel`
- `GET /kernel/interrupts`
- `POST /kernel/tasks`

## Current state

R1 foundation is **partial**: in-memory goal/context/budget state is implemented
and tested. Durable checkpoints, resume, and desktop mission-control surfaces
belong to later phases (R2 / R8).
