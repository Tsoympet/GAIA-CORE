# Changelog

## Unreleased

### Added

- Opt-in cognitive continuity journal (`gaia.continuity`) backed by local SQLite.
- Versioned schema v1 and a forced downgrade to an empty schema version 0.
- Validated task state machine, append-only transitions, and hash-linked checkpoints.
- Recovery that interrupts in-flight work, quarantines unpublished or corrupt snapshots, redacts secrets, and revokes approvals.
- Process-local approval grants, work branches, resume, audit export, and live goal deletion.
- Kernel and CLI wiring via `continuity_path` / `--continuity-db`, plus `/kernel/continuity/*` routes.
- `gaia continuity` inspects an existing journal and does not run recovery.

### Notes

- Continuity is not enabled for the default in-memory runtime.
- Checkpoint hashes detect corruption and naive tampering. They are not cryptographic immutability.
- No new third-party dependencies were added. SQLite and hashing use the Python standard library.
