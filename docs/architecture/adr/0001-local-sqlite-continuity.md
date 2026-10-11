# ADR 0001: Local SQLite continuity journal

## Status

Accepted for the R2 continuity milestone. The capability remains partial.

## Context

The Cognitive Kernel kept goals, working context, budgets, and interrupts in
process memory. A restart dropped that state. GAIA is local-first, and the
workspace store already uses SQLite from the Python standard library.

## Decision

Persist continuity in a SQLite file addressed by `continuity_path`.

- Schema version 2 is migrated on open. Version 2 stores session workspace id
  and redacted metadata beside the session id and user id.
- Checkpoints are published inside one transaction. The stored payload is
  canonical JSON and is linked by SHA-256 to the previous published payload.
- Recovery, not every read, normalizes in-flight work and revokes approvals.
- A lock file records the holder pid. A live holder blocks recovery so a
  second process cannot mark a running task interrupted.
- No new third-party database dependency is added.

PostgreSQL, Redis, and external object stores stay out of this path. They
would make local and offline operation depend on another service.

## Consequences

- Operators can restart a configured runtime and reload goals, context, and
  task state.
- Approvals and credentials are not part of recovered authority.
- The hash chain is tamper-evident against accidental corruption and naive
  payload edits. It is not a cryptographic ledger against a privileged writer.
- Multi-writer replication and desktop presentation are not provided by this
  decision. Field encryption is covered by ADR 0003.
- Schema downgrade to version 0 drops continuity tables and must be forced
  when published checkpoints exist.

## Rollback

Stop the runtime. Copy the SQLite file. Call `ContinuityStore.rollback_schema(0, force=True)`
only after exporting `export_audit_bundle()`. Opening the file again recreates
an empty version 1 schema. Restoring the copied file returns the previous
journal. Application code from this milestone can also be reverted; the schema
is not read by older runtimes because those runtimes do not open the file
unless `continuity_path` is set.
