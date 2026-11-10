"""Repository and process observations recorded by the continuity journal."""

from __future__ import annotations

import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gaia.continuity.errors import ContinuityIntegrityError
from gaia.continuity.journal import ContinuityJournal
from gaia.continuity.snapshots import ProcessObservation, observe_repository
from gaia.continuity.store import ContinuityStore
from gaia.core.runtime import GaiaRuntime, create_runtime
from gaia.kernel.goal_manager import Goal, GoalStatus
from gaia.security.field_cipher import FieldCipher


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "gaia@example.com")
    _git(path, "config", "user.name", "GAIA")
    (path / "note.txt").write_text("visible-body-marker", encoding="utf-8")
    _git(path, "add", "note.txt")
    _git(path, "commit", "-m", "init")
    return path


def _head(path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_repository_observation_records_head_without_file_contents(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    _git(repo, "remote", "add", "origin", "https://user:ghp_secret@github.com/example/repo.git")
    (repo / "password.txt").write_text("do-not-store-this-secret", encoding="utf-8")
    observation = observe_repository(repo)
    assert observation.available is True
    assert observation.modifies_worktree is False
    assert observation.head_commit == _head(repo)
    assert observation.dirty is True
    assert "[redacted]" in observation.changed_paths
    assert "password.txt" not in observation.changed_paths
    assert "visible-body-marker" not in " ".join(observation.changed_paths)

    journal_path = tmp_path / "continuity.sqlite3"
    journal = ContinuityJournal(
        ContinuityStore(journal_path),
        repository_root=repo,
        model_id="ollama",
        model_configuration={"provider": "ollama", "api_key": "hidden"},
        tool_policy={"sandbox_required": True},
    )
    checkpoint = journal.publish(reason="observe", kernel_id="kernel-1")
    assert checkpoint.payload_json is not None
    assert "ghp_secret" not in checkpoint.payload_json
    assert "do-not-store-this-secret" not in checkpoint.payload_json
    assert "visible-body-marker" not in checkpoint.payload_json
    assert b"ghp_secret" not in journal_path.read_bytes()
    assert b"do-not-store-this-secret" not in journal_path.read_bytes()
    stored = ContinuityStore(journal_path).get_repository_snapshot(checkpoint.checkpoint_id)
    assert stored is not None
    assert stored.modifies_worktree is False
    assert stored.changed_paths_sha256 == observation.changed_paths_sha256
    process = ContinuityStore(journal_path).get_process_snapshot(checkpoint.checkpoint_id)
    assert process is not None
    assert process.resumes_process is False
    assert process.switches_model is False
    assert process.model_id == "ollama"


def test_missing_root_and_non_repo_are_explicit(tmp_path: Path) -> None:
    absent = observe_repository(None)
    assert absent.available is False
    assert absent.note == "no repository root configured"
    plain = tmp_path / "plain"
    plain.mkdir()
    observed = observe_repository(plain)
    assert observed.available is False
    assert observed.note == "not a git worktree"


def test_rollback_does_not_change_the_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    store = ContinuityStore(tmp_path / "continuity.sqlite3")
    journal = ContinuityJournal(store, repository_root=repo, model_id="ollama")
    baseline = journal.publish(reason="baseline", kernel_id="kernel-1")
    original = _head(repo)
    (repo / "later.txt").write_text("later", encoding="utf-8")
    _git(repo, "add", "later.txt")
    _git(repo, "commit", "-m", "later")
    moved = _head(repo)
    assert moved != original
    journal.rollback(baseline.checkpoint_id, kernel_id="kernel-1")
    assert _head(repo) == moved
    assert (repo / "later.txt").exists()


@pytest.mark.asyncio
async def test_resume_refuses_a_diverged_worktree_or_model(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    path = tmp_path / "continuity.sqlite3"
    runtime = create_runtime(continuity_path=path, repository_root=repo)
    runtime.kernel.interrupts.request_global("stop before execution")
    interrupted = await _run(runtime, "Summarize the local runtime")
    assert interrupted.status is GoalStatus.INTERRUPTED
    runtime.kernel.interrupts.clear_global()
    (repo / "drift.txt").write_text("drift", encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not modify the worktree"):
        await runtime.kernel.resume(interrupted.id)

    clean = create_runtime(continuity_path=tmp_path / "clean.sqlite3")
    clean.kernel.interrupts.request_global("stop before execution")
    waiting = await _run(clean, "Summarize the local runtime")
    clean.kernel.interrupts.clear_global()
    journal = clean.kernel.continuity
    assert journal is not None
    journal.model_id = "other-model"
    with pytest.raises(RuntimeError, match="does not switch models"):
        await clean.kernel.resume(waiting.id)


def test_schema_rollback_drops_snapshots_and_reopens_from_the_payload(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    path = tmp_path / "continuity.sqlite3"
    journal = ContinuityJournal(ContinuityStore(path), repository_root=repo, model_id="ollama")
    checkpoint = journal.publish(reason="keep", kernel_id="kernel-1")
    store = ContinuityStore(path)
    assert store.rollback_schema(2, force=True) == 2
    with sqlite3.connect(path) as connection:
        names = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert "repository_snapshots" not in names
    assert "process_snapshots" not in names
    assert "checkpoints" in names

    restored = ContinuityStore(path)
    assert restored.schema_version() == 3
    snapshot = restored.get_repository_snapshot(checkpoint.checkpoint_id)
    assert snapshot is not None
    assert snapshot.head_commit == _head(repo)
    assert snapshot.modifies_worktree is False
    assert restored.verify_checkpoint(checkpoint.checkpoint_id) is True


def test_tampered_snapshot_index_blocks_resume(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    journal = ContinuityJournal(
        ContinuityStore(path),
        model_id="ollama",
        model_configuration={"name": "ollama"},
        tool_policy={"sandbox_required": True},
    )
    checkpoint = journal.publish(reason="observe", kernel_id="kernel-1")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE process_snapshots SET model_id = ? WHERE checkpoint_id = ?",
            ("replaced", checkpoint.checkpoint_id),
        )
    with pytest.raises(ContinuityIntegrityError, match="index does not match"):
        journal.assert_resume_current()


def test_snapshot_paths_are_sealed_with_the_data_key(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    distinctive = tmp_path / "workspace-secret-root"
    distinctive.mkdir()
    _git(distinctive, "init")
    path = tmp_path / "continuity.sqlite3"
    journal = ContinuityJournal(ContinuityStore(path), repository_root=repo)
    journal.publish(reason="observe", kernel_id="kernel-1")
    assert str(repo.resolve()).encode() in path.read_bytes()
    sealed = ContinuityStore(path, cipher=FieldCipher(b"k" * 32))
    assert str(repo.resolve()).encode() not in path.read_bytes()
    loaded = sealed.list_repository_snapshots()
    assert loaded[0].repository_root == str(repo.resolve())
    assert sealed.verify_chain() is True


def test_process_claim_cannot_promise_a_model_switch(tmp_path: Path) -> None:
    observation = ProcessObservation(
        kernel_id="kernel-1",
        process_nonce="nonce",
        python_version="3.12.0",
        pid=1,
        switches_model=True,
        captured_at=datetime.now(UTC),
    )
    with pytest.raises(ContinuityIntegrityError, match="cannot resume a process or switch models"):
        ContinuityStore(tmp_path / "continuity.sqlite3").publish_checkpoint(
            reason="bad",
            kernel_id="kernel-1",
            process=observation,
        )


async def _run(runtime: GaiaRuntime, objective: str) -> Goal:
    result = await runtime.kernel.run(objective, "session-snap")
    return result.goal
