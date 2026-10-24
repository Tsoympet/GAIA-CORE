"""Versioned SQLite schema for the continuity journal."""

from __future__ import annotations

SCHEMA_VERSION = 4

MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    goal_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL,
    goal_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contexts (
    goal_id TEXT PRIMARY KEY,
    context_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_runs (
    task_id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    action_fingerprint TEXT NOT NULL,
    task_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_transitions (
    transition_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    parent_checkpoint_id TEXT,
    schema_version INTEGER NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    publication TEXT NOT NULL,
    created_at TEXT NOT NULL,
    kernel_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS branches (
    branch_id TEXT PRIMARY KEY,
    parent_checkpoint_id TEXT NOT NULL,
    fork_reason TEXT NOT NULL,
    memory_snapshot_hash TEXT NOT NULL,
    project_snapshot_hash TEXT NOT NULL,
    model_configuration_json TEXT NOT NULL,
    tool_policy_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_events (
    approval_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    action_fingerprint TEXT NOT NULL,
    approver TEXT NOT NULL,
    decision TEXT NOT NULL,
    process_nonce TEXT NOT NULL,
    reusable INTEGER NOT NULL,
    expired INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine (
    record_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_session ON goals(session_id);
CREATE INDEX IF NOT EXISTS idx_transitions_task ON task_transitions(task_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_publication ON checkpoints(publication);
"""

MIGRATION_V2 = """
ALTER TABLE sessions ADD COLUMN workspace_id TEXT;
ALTER TABLE sessions ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';
"""

MIGRATION_V3 = """
CREATE TABLE IF NOT EXISTS repository_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    checkpoint_id TEXT NOT NULL,
    repository_root TEXT NOT NULL,
    available INTEGER NOT NULL,
    head_commit TEXT,
    branch TEXT,
    detached INTEGER NOT NULL,
    dirty INTEGER NOT NULL,
    changed_path_count INTEGER NOT NULL,
    changed_paths_sha256 TEXT NOT NULL,
    changed_paths_json TEXT NOT NULL,
    changed_paths_truncated INTEGER NOT NULL,
    modifies_worktree INTEGER NOT NULL,
    note TEXT NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS process_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    checkpoint_id TEXT NOT NULL,
    kernel_id TEXT NOT NULL,
    process_nonce TEXT NOT NULL,
    python_version TEXT NOT NULL,
    pid INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    model_configuration_sha256 TEXT NOT NULL,
    tool_policy_sha256 TEXT NOT NULL,
    resumes_process INTEGER NOT NULL,
    switches_model INTEGER NOT NULL,
    note TEXT NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repository_snapshots_checkpoint
    ON repository_snapshots(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_process_snapshots_checkpoint
    ON process_snapshots(checkpoint_id);
"""

DROP_V3 = """
DROP TABLE IF EXISTS repository_snapshots;
DROP TABLE IF EXISTS process_snapshots;
"""

MIGRATION_V4 = """
CREATE TABLE IF NOT EXISTS model_migrations (
    migration_id TEXT PRIMARY KEY,
    from_checkpoint_id TEXT NOT NULL,
    to_checkpoint_id TEXT NOT NULL,
    from_model_id TEXT NOT NULL,
    to_model_id TEXT NOT NULL,
    from_model_configuration_sha256 TEXT NOT NULL,
    to_model_configuration_sha256 TEXT NOT NULL,
    reason TEXT NOT NULL,
    automatic INTEGER NOT NULL,
    executes_task INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_model_migrations_to_checkpoint
    ON model_migrations(to_checkpoint_id);
"""

DROP_V4 = """
DROP TABLE IF EXISTS model_migrations;
"""

DROP_V1 = """
DROP TABLE IF EXISTS model_migrations;
DROP TABLE IF EXISTS repository_snapshots;
DROP TABLE IF EXISTS process_snapshots;
DROP TABLE IF EXISTS quarantine;
DROP TABLE IF EXISTS approval_events;
DROP TABLE IF EXISTS branches;
DROP TABLE IF EXISTS checkpoints;
DROP TABLE IF EXISTS task_transitions;
DROP TABLE IF EXISTS task_runs;
DROP TABLE IF EXISTS contexts;
DROP TABLE IF EXISTS goals;
DROP TABLE IF EXISTS sessions;
"""
