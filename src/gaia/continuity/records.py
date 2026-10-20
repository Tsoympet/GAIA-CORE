"""Typed continuity records persisted by the local journal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from gaia.continuity.task_state import TaskState


class TaskRun(BaseModel):
    """One persistent task run bound to a kernel goal."""

    task_id: str
    goal_id: str
    session_id: str
    state: TaskState
    action_fingerprint: str
    objective: str
    budget: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class Checkpoint(BaseModel):
    """A published or quarantined continuity snapshot."""

    checkpoint_id: str
    parent_checkpoint_id: str | None
    schema_version: int
    reason: str
    payload_sha256: str
    previous_hash: str
    publication: str
    created_at: datetime
    kernel_id: str
    payload_json: str | None = None


class WorkBranch(BaseModel):
    """A fork of a verified checkpoint.

    Branches record the parent checkpoint, snapshot hashes, model configuration,
    and tool policy. They do not copy approval tokens or credentials.
    """

    branch_id: str
    parent_checkpoint_id: str
    fork_reason: str
    memory_snapshot_hash: str
    project_snapshot_hash: str
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    tool_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ApprovalEvent(BaseModel):
    """Audit record of an approval decision.

    ``reusable`` is always false. Recovery marks every event expired, and the
    live grant exists only in the process that recorded it.
    """

    approval_id: str
    task_id: str
    goal_id: str
    action_fingerprint: str
    approver: str
    decision: str
    process_nonce: str
    reusable: bool = False
    expired: bool = False
    created_at: datetime


class RepositorySnapshot(BaseModel):
    """Read-only observation of a git worktree at checkpoint publication.

    ``modifies_worktree`` is always false. Rollback restores journal rows and
    does not check out commits or edit files.
    """

    snapshot_id: str
    checkpoint_id: str
    repository_root: str = ""
    available: bool = False
    head_commit: str | None = None
    branch: str | None = None
    detached: bool = False
    dirty: bool = False
    changed_path_count: int = 0
    changed_paths_sha256: str = ""
    changed_paths: list[str] = Field(default_factory=list)
    changed_paths_truncated: bool = False
    modifies_worktree: bool = False
    note: str
    captured_at: datetime


class ProcessSnapshot(BaseModel):
    """Read-only observation of the process that published a checkpoint.

    The pid and process nonce identify the publisher. They are not
    authorization, and resume does not revive that process or switch models.
    """

    snapshot_id: str
    checkpoint_id: str
    kernel_id: str
    process_nonce: str
    python_version: str
    pid: int
    model_id: str = ""
    model_configuration_sha256: str = ""
    tool_policy_sha256: str = ""
    resumes_process: bool = False
    switches_model: bool = False
    note: str
    captured_at: datetime


class ModelMigration(BaseModel):
    """Audited move from one model observation to the current model.

    ``executes_task`` is always false. The migration does not run the task,
    grant approval, change tool policy, or modify the worktree. Resume may
    rerun the task afterward under the current model.
    """

    migration_id: str
    from_checkpoint_id: str
    to_checkpoint_id: str
    from_model_id: str
    to_model_id: str
    from_model_configuration_sha256: str
    to_model_configuration_sha256: str
    reason: str
    automatic: bool = True
    executes_task: bool = False
    created_at: datetime


class ModelMigrationRequest(BaseModel):
    """Fields known before the destination checkpoint id exists."""

    from_checkpoint_id: str
    from_model_id: str
    to_model_id: str
    from_model_configuration_sha256: str
    to_model_configuration_sha256: str
    reason: str
    automatic: bool = True
    executes_task: bool = False


class QuarantineRecord(BaseModel):
    """Dead-letter record for drafts, tampered snapshots, or deletions."""

    record_id: str
    kind: str
    reason: str
    payload_json: str
    created_at: datetime


class RecoveryReport(BaseModel):
    """Result of opening a continuity journal after a process start."""

    schema_version: int
    interrupted_goal_ids: list[str] = Field(default_factory=list)
    revoked_approval_ids: list[str] = Field(default_factory=list)
    quarantined_ids: list[str] = Field(default_factory=list)
    integrity_ok: bool = True
    mutated: bool = False
    notes: list[str] = Field(default_factory=list)
