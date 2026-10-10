# Cognitive Continuity (R2, partial)

Cognitive continuity keeps kernel goals, working context, and task state on the
local machine so a restarted process can inspect what happened and resume only
when that is safe.

Continuity is optional. `create_runtime()` stays in-memory until the caller
passes `continuity_path`. The CLI can enable it with `--continuity-db`.

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

## Schema

Schema version 1 is applied automatically. `rollback_schema(0, force=True)`
drops continuity tables. Rollback is refused while published checkpoints exist
unless `force` is set, because a downgrade destroys that history. Re-opening
the database applies version 1 again. Export an audit bundle first.

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

- Storage is local SQLite and is not encrypted at rest.
- The hash chain detects corruption and naive edits. A privileged local writer
  can recompute it. GAIA does not claim cryptographic immutability.
- Internal orchestrator planning is recorded as `classified → executing` when
  the kernel does not receive a separate plan object. `planned` remains a
  valid state for callers that do.
- Desktop mission control is not wired to this journal.
- The Memory Organism and Evidence Ledger are a separate opt-in SQLite file.
  They do not yet store continuity checkpoint ids. Do not put goal state in
  the organism file.
