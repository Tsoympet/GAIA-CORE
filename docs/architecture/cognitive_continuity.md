# Cognitive Continuity (R2, partial)

Cognitive continuity keeps a hash-linked journal of kernel goals, working
context, and task state on the local machine so a restarted process can inspect
what happened and resume only when that is safe.

`KernelStore` is the live goal, context, and budget store. It is always
attached (`:memory:` in tests, `.gaia/kernel.sqlite3` for the CLI). The
continuity journal is optional and sits on top of that store. Pass
`continuity_path` or `--continuity-db` to record task transitions, redacted
context, checkpoints, and crash recovery. On startup the kernel hydrates
`KernelStore` first. When a journal is configured, recovery overlays live
goals and contexts, then those live rows are written back to `KernelStore`.

## What is durable

- Goals, bounded working context, and task runs in a local SQLite file.
- An explicit task state machine:
  `created → classified → planned → approved_if_required → executing → verifying → completed`,
  plus `blocked`, `waiting_for_user`, `cancelled`, `failed`, `quarantined`,
  `rolled_back`, and `interrupted`.
- Append-only transition history.
- Hash-linked checkpoints published in one SQLite transaction.
- Work branches that record a parent checkpoint, snapshot hashes, model
  configuration, and tool policy.
- Approval audit events that are marked non-reusable.

## Recovery rules

Opening a runtime with a continuity path recovers the journal before new work
starts:

- Draft checkpoints that were never published are quarantined.
- Published checkpoints whose payload does not match the stored digest are
  quarantined. The hash chain is not treated as proof of cryptographic
  immutability.
- Goals left `active`, and tasks left `executing` or `verifying`, become
  `interrupted`. They are not continued automatically.
- `approved_if_required` becomes `waiting_for_user`. Approval does not survive
  restart.
- Sensitive metadata and context keys (`approval_token`, `api_key`, `password`,
  and similar names) are redacted before they are stored and again on recovery.
- A second live process that holds the journal lock is not interrupted.

Resume re-runs policy checks. A waiting task runs only when the same process
holds a live grant for that goal's action fingerprint. A database row is not
authorization.

## Sessions

A configured runtime persists the session id, user id, workspace id, creation
time, and metadata when a task is submitted. Restart restores those fields.
Secret metadata keys are redacted before they are stored and again on recovery.
Approval grants are not part of the session record.

Published checkpoints include session rows. Rollback to a checkpoint that has
a session snapshot replaces live session rows. A checkpoint written before
schema version 2 has no session snapshot, and rollback leaves the live session
rows in place.

## Schema

Schema version 2 is applied automatically. Version 2 adds `workspace_id` and
`metadata_json` to `sessions`. `rollback_schema(1)` drops those columns and
keeps the version 1 session id, user id, and creation time.
`rollback_schema(0, force=True)` drops continuity tables. Rollback to version 0
is refused while published checkpoints exist unless `force` is set, because a
downgrade destroys that history. Re-opening the database applies version 2
again. Export an audit bundle first.

Live goal deletion removes the working rows and writes a tombstone with the
goal id and reason. It does not rewrite published checkpoints.

## Operator API

- `GET /kernel/continuity`
- `GET /kernel/continuity/checkpoints`
- `POST /kernel/continuity/checkpoints`
- `GET /kernel/continuity/checkpoints/{checkpoint_id}`
- `POST /kernel/continuity/checkpoints/{checkpoint_id}/verify`
- `POST /kernel/continuity/rollback`
- `GET /kernel/continuity/tasks`
- `POST /kernel/continuity/tasks/{goal_id}/resume`
- `POST /kernel/continuity/tasks/{goal_id}/approval`
- `GET|POST /kernel/continuity/branches`
- `POST /kernel/continuity/branches/{branch_id}/materialize`
- `GET /kernel/continuity/audit`
- `POST /kernel/continuity/goals/{goal_id}/delete`

If no journal is configured, `GET /kernel/continuity` returns status
`unavailable`. It does not report a durable journal that is not there.

`gaia continuity --db <path>` inspects an existing file and does not run
recovery. `gaia run` and `gaia serve` accept `--continuity-db`.

## Current limitations

- Storage is local SQLite. Secret JSON is sealed with AES-GCM only when a
  data key is configured. The hash chain is unchanged by that seal.
- The hash chain detects corruption and naive edits. A privileged local writer
  can recompute it. GAIA does not claim cryptographic immutability.
- Internal orchestrator planning is recorded as `classified → executing` when
  the kernel does not receive a separate plan object. `planned` remains a
  valid state for callers that do.
- Desktop mission control can inspect status, publish a checkpoint, verify the
  hash chain, and list task runs. It does not stream continuity events, and it
  does not present the chain as cryptographic immutability.
- Restored sessions do not carry process-local approval grants.
- When an organism is configured on the same runtime, published checkpoints
  are cited in the evidence ledger by digest. The payload stays in the
  continuity journal. Do not put goal state in the organism file.
