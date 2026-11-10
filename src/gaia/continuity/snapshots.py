"""Read-only repository and process observations for continuity checkpoints."""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from gaia.continuity.codec import canonical_json, sha256_text
from gaia.continuity.records import ProcessSnapshot, RepositorySnapshot
from gaia.continuity.redaction import is_sensitive_key

PATH_LIST_LIMIT = 32
_GIT_TIMEOUT_SECONDS = 5


class RepositoryObservation(BaseModel):
    """Git worktree observation captured before a checkpoint is published."""

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
    note: str = "observation only; rollback does not modify the worktree"
    captured_at: datetime


class ProcessObservation(BaseModel):
    """Process observation captured before a checkpoint is published."""

    kernel_id: str
    process_nonce: str
    python_version: str
    pid: int
    model_id: str = ""
    model_configuration_sha256: str = ""
    tool_policy_sha256: str = ""
    resumes_process: bool = False
    switches_model: bool = False
    note: str = "observation only; resume does not revive this process or switch models"
    captured_at: datetime


class EnvironmentComparison(BaseModel):
    """Difference between a stored observation and this process."""

    comparable: bool = False
    repository_diverged: bool = False
    repository_recheck_required: bool = False
    model_switched: bool = False
    tool_policy_changed: bool = False
    index_matches_payload: bool = True
    modifies_worktree: bool = False
    resumes_process: bool = False
    switches_model: bool = False
    notes: list[str] = Field(default_factory=list)

    def blocks_resume(self) -> bool:
        """Return whether resume must stop before re-running the goal."""
        return bool(self.notes)


def observe_repository(root: Path | None) -> RepositoryObservation:
    """Read git HEAD and status. This function does not write to the worktree."""
    captured_at = _now()
    if root is None:
        return RepositoryObservation(
            available=False,
            note="no repository root configured",
            captured_at=captured_at,
        )
    try:
        resolved = root.expanduser().resolve()
    except OSError:
        return RepositoryObservation(
            repository_root=str(root),
            available=False,
            note="repository root could not be resolved",
            captured_at=captured_at,
        )
    if not resolved.exists():
        return RepositoryObservation(
            repository_root=str(resolved),
            available=False,
            note="repository root does not exist",
            captured_at=captured_at,
        )
    try:
        inside = _git(resolved, "rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        return RepositoryObservation(
            repository_root=str(resolved),
            available=False,
            note="git is not available",
            captured_at=captured_at,
        )
    except subprocess.TimeoutExpired:
        return RepositoryObservation(
            repository_root=str(resolved),
            available=False,
            note="git observation timed out",
            captured_at=captured_at,
        )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return RepositoryObservation(
            repository_root=str(resolved),
            available=False,
            note="not a git worktree",
            captured_at=captured_at,
        )
    head = _git(resolved, "rev-parse", "HEAD")
    branch = _git(resolved, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(resolved, "status", "--porcelain=v1", "-z", "--untracked-files=normal")
    branch_name = branch.stdout.strip()
    detached = branch_name == "HEAD" or branch.returncode != 0
    paths = _changed_paths(status.stdout)
    redacted = sorted(redact_repository_path(path) for path in paths)
    digest = sha256_text(canonical_json(redacted))
    note = "observation only; rollback does not modify the worktree"
    if head.returncode != 0:
        note = "worktree has no commits; rollback does not modify the worktree"
    return RepositoryObservation(
        repository_root=str(resolved),
        available=True,
        head_commit=None if head.returncode != 0 else head.stdout.strip(),
        branch=None if detached else branch_name,
        detached=detached,
        dirty=bool(paths),
        changed_path_count=len(paths),
        changed_paths_sha256=digest,
        changed_paths=redacted[:PATH_LIST_LIMIT],
        changed_paths_truncated=len(redacted) > PATH_LIST_LIMIT,
        modifies_worktree=False,
        note=note,
        captured_at=captured_at,
    )


def observe_process(
    *,
    kernel_id: str,
    process_nonce: str,
    model_id: str,
    model_configuration: dict[str, Any],
    tool_policy: dict[str, Any],
) -> ProcessObservation:
    """Hash the redacted model and tool configuration for this process."""
    from gaia.continuity.redaction import redact_mapping

    redacted_model = redact_mapping(model_configuration)
    redacted_policy = redact_mapping(tool_policy)
    return ProcessObservation(
        kernel_id=kernel_id,
        process_nonce=process_nonce,
        python_version=platform.python_version(),
        pid=os.getpid(),
        model_id=model_id,
        model_configuration_sha256=sha256_text(canonical_json(redacted_model)),
        tool_policy_sha256=sha256_text(canonical_json(redacted_policy)),
        resumes_process=False,
        switches_model=False,
        captured_at=_now(),
    )


def compare_environment(
    *,
    repository_payload: dict[str, Any] | None,
    process_payload: dict[str, Any] | None,
    repository_row: RepositorySnapshot | None,
    process_row: ProcessSnapshot | None,
    live_repository: RepositoryObservation,
    live_process: ProcessObservation,
) -> EnvironmentComparison:
    """Compare the authoritative payload with this process and the side index."""
    if repository_payload is None and process_payload is None:
        return EnvironmentComparison(comparable=False)
    notes: list[str] = []
    index_ok = True
    repository_diverged = False
    recheck_required = False
    model_switched = False
    policy_changed = False
    modifies_worktree = False
    resumes_process = False
    switches_model = False

    if repository_payload is not None:
        recorded = RepositoryObservation.model_validate(repository_payload)
        if recorded.modifies_worktree:
            modifies_worktree = True
            notes.append("repository snapshot claims it modifies the worktree")
        if repository_row is None or not _same_repository(recorded, repository_row):
            index_ok = False
            notes.append("repository snapshot index does not match the checkpoint payload")
        elif recorded.available and not live_repository.available:
            recheck_required = True
            notes.append(
                "repository observation cannot be rechecked because no worktree is available"
            )
        elif recorded.available and live_repository.available and _repository_diverged(
            recorded, live_repository
        ):
            repository_diverged = True
            notes.append(
                "repository diverged from the checkpoint observation; "
                "resume does not modify the worktree"
            )

    if process_payload is not None:
        recorded_process = ProcessObservation.model_validate(process_payload)
        if recorded_process.resumes_process:
            resumes_process = True
            notes.append("process snapshot claims it resumes the publishing process")
        if recorded_process.switches_model:
            switches_model = True
            notes.append("process snapshot claims it switches models")
        if process_row is None or not _same_process(recorded_process, process_row):
            index_ok = False
            notes.append("process snapshot index does not match the checkpoint payload")
        elif (
            recorded_process.model_id != live_process.model_id
            or recorded_process.model_configuration_sha256
            != live_process.model_configuration_sha256
        ):
            model_switched = True
            notes.append(
                "model configuration differs from the checkpoint observation; "
                "resume does not switch models"
            )
        elif recorded_process.tool_policy_sha256 != live_process.tool_policy_sha256:
            policy_changed = True
            notes.append(
                "tool policy differs from the checkpoint observation; "
                "resume does not apply a different policy"
            )

    return EnvironmentComparison(
        comparable=True,
        repository_diverged=repository_diverged,
        repository_recheck_required=recheck_required,
        model_switched=model_switched,
        tool_policy_changed=policy_changed,
        index_matches_payload=index_ok,
        modifies_worktree=modifies_worktree,
        resumes_process=resumes_process,
        switches_model=switches_model,
        notes=notes,
    )


def redact_repository_path(path: str) -> str:
    """Hide path entries whose names look like secrets. File contents are never stored."""
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    for part in parts:
        stem = part[1:] if part.startswith(".") else part
        stem = stem.split(".", 1)[0]
        if is_sensitive_key(part) or is_sensitive_key(stem):
            return "[redacted]"
    return normalized


def repository_section(snapshot: RepositorySnapshot) -> dict[str, Any]:
    """Return the payload fields of a repository snapshot."""
    data = snapshot.model_dump(mode="json")
    data.pop("snapshot_id", None)
    data.pop("checkpoint_id", None)
    return data


def process_section(snapshot: ProcessSnapshot) -> dict[str, Any]:
    """Return the payload fields of a process snapshot."""
    data = snapshot.model_dump(mode="json")
    data.pop("snapshot_id", None)
    data.pop("checkpoint_id", None)
    return data


def _same_repository(recorded: RepositoryObservation, row: RepositorySnapshot) -> bool:
    return recorded.model_dump(mode="json") == repository_section(row)


def _same_process(recorded: ProcessObservation, row: ProcessSnapshot) -> bool:
    return recorded.model_dump(mode="json") == process_section(row)


def _repository_diverged(recorded: RepositoryObservation, live: RepositoryObservation) -> bool:
    return (
        recorded.head_commit != live.head_commit
        or recorded.branch != live.branch
        or recorded.detached != live.detached
        or recorded.dirty != live.dirty
        or recorded.changed_paths_sha256 != live.changed_paths_sha256
    )


def _changed_paths(porcelain: str) -> list[str]:
    if not porcelain:
        return []
    tokens = porcelain.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if len(token) < 4:
            index += 1
            continue
        status = token[:2]
        path = token[3:]
        if path:
            paths.append(path)
        index += 1
        if "R" in status or "C" in status:
            if index < len(tokens) and tokens[index]:
                paths.append(tokens[index])
            index += 1
    return paths


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


def _now() -> datetime:
    return datetime.now(UTC)
