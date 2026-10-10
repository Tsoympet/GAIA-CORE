"""SQLite continuity journal with crash-safe checkpoint publication."""

from __future__ import annotations

import atexit
import json
import os
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from gaia.continuity.codec import canonical_json, json_object, sha256_text
from gaia.continuity.errors import ContinuityIntegrityError, ContinuityLockedError
from gaia.continuity.records import (
    ApprovalEvent,
    Checkpoint,
    QuarantineRecord,
    RecoveryReport,
    TaskRun,
    WorkBranch,
)
from gaia.continuity.redaction import is_sensitive_key, redact_mapping, redact_value
from gaia.continuity.schema import DROP_V1, MIGRATION_V1
from gaia.continuity.schema import SCHEMA_VERSION as SCHEMA_VERSION
from gaia.continuity.task_state import (
    UNSAFE_RECOVERY_STATES,
    TaskState,
    validate_transition,
)
from gaia.kernel.context_manager import WorkingContext
from gaia.kernel.goal_manager import Goal, GoalStatus
from gaia.security.field_cipher import (
    DataKeyError,
    FieldCipher,
    open_field,
    seal_field,
    seal_if_plain,
)

GENESIS_HASH = "genesis"
_RELEASED_LOCKS: set[str] = set()


def _pid_alive(pid_text: str) -> bool:
    try:
        pid = int(pid_text)
    except ValueError:
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _release_lock_file(path: Path, pid: int) -> None:
    key = str(path)
    if key in _RELEASED_LOCKS:
        return
    try:
        if path.exists() and path.read_text(encoding="utf-8").strip() == str(pid):
            path.unlink()
            _RELEASED_LOCKS.add(key)
    except OSError:
        return


def _now() -> datetime:
    return datetime.now(UTC)


def _as_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContinuityIntegrityError("expected a JSON object")
    mapped: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ContinuityIntegrityError("expected string JSON keys")
        mapped[key] = item
    return mapped


def _redacted_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return redact_mapping(value)


class ContinuityStore:
    """Local-first durable journal for goals, task state, and checkpoints.

    The hash chain detects corruption and naive payload edits. It does not
    provide cryptographic immutability against a privileged local writer.
    """

    def __init__(self, db_path: Path | str, *, cipher: FieldCipher | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.db_path.with_name(self.db_path.name + ".lock")
        self._lock_held = False
        self.cipher = cipher
        self.checkpoint_witness: Callable[[Checkpoint], None] | None = None
        self.migrate()
        if cipher is not None:
            self.reseal_plaintext()

    def migrate(self) -> int:
        """Apply pending schema upgrades and return the current version."""
        with self._transaction() as connection:
            self._bootstrap(connection)
            current = self._schema_version(connection)
            if current < 1:
                _execute_sql_script(connection, MIGRATION_V1)
                self._record_migration(connection, 1, "continuity_initial")
                current = 1
            if current > SCHEMA_VERSION:
                raise ContinuityIntegrityError(
                    f"continuity schema {current} is newer than this build ({SCHEMA_VERSION})"
                )
            return current

    def schema_version(self) -> int:
        """Return the applied schema version, migrating an empty database first."""
        return self.migrate()

    def reseal_plaintext(self) -> int:
        """Encrypt plaintext secret fields. Checkpoint digests stay hashes of plaintext."""
        if self.cipher is None:
            return 0
        self._ensure_lock()
        changed = 0
        with self._transaction() as connection:
            changed += _reseal_column(connection, self.cipher, "goals", "goal_id", "goal_json")
            changed += _reseal_column(
                connection, self.cipher, "contexts", "goal_id", "context_json"
            )
            changed += _reseal_column(
                connection, self.cipher, "task_runs", "task_id", "task_json"
            )
            changed += _reseal_column(
                connection, self.cipher, "checkpoints", "checkpoint_id", "payload_json"
            )
            changed += _reseal_column(
                connection, self.cipher, "checkpoints", "checkpoint_id", "reason"
            )
            changed += _reseal_column(
                connection, self.cipher, "quarantine", "record_id", "payload_json"
            )
            changed += _reseal_column(
                connection, self.cipher, "task_transitions", "transition_id", "reason"
            )
            changed += _reseal_column(
                connection, self.cipher, "branches", "branch_id", "fork_reason"
            )
            changed += _reseal_column(
                connection, self.cipher, "branches", "branch_id", "model_configuration_json"
            )
            changed += _reseal_column(
                connection, self.cipher, "branches", "branch_id", "tool_policy_json"
            )
        return changed

    def _seal(self, plaintext: str) -> str:
        return seal_field(self.cipher, plaintext)

    def _open(self, stored: str) -> str:
        return open_field(self.cipher, stored)

    def rollback_schema(self, target: int, *, force: bool = False) -> int:
        """Roll the continuity schema back to ``target``.

        Version 0 drops continuity tables. Published history is kept unless
        ``force`` is set, because a downgrade destroys checkpoint rows.
        """
        if target < 0 or target > SCHEMA_VERSION:
            raise ValueError(f"unsupported schema target: {target}")
        self.migrate()
        self._ensure_lock()
        with self._transaction() as connection:
            current = self._schema_version(connection)
            if target > current:
                raise ValueError("schema rollback target is newer than the applied version")
            if target == current:
                return current
            published = connection.execute(
                "SELECT COUNT(*) AS count FROM checkpoints WHERE publication = 'published'"
            ).fetchone()
            published_count = int(published["count"]) if published is not None else 0
            if published_count and not force:
                raise ContinuityIntegrityError(
                    "schema rollback would drop published continuity history; "
                    "export an audit bundle and pass force=True"
                )
            if target == 0 and current >= 1:
                _execute_sql_script(connection, DROP_V1)
                connection.execute("DELETE FROM schema_migrations WHERE version = 1")
            return self._schema_version(connection)

    def recover(self) -> RecoveryReport:
        """Quarantine incomplete writes, revoke approvals, and stop in-flight work."""
        version = self.migrate()
        self._ensure_lock()
        interrupted: list[str] = []
        revoked: list[str] = []
        quarantined: list[str] = []
        notes: list[str] = []
        mutated = False

        with self._transaction() as connection:
            for row in connection.execute(
                "SELECT checkpoint_id, payload_json FROM checkpoints WHERE publication = 'draft'"
            ):
                checkpoint_id = str(row["checkpoint_id"])
                self._quarantine_on(
                    connection,
                    kind="abandoned_draft",
                    reason="draft checkpoint was not published before the process stopped",
                    payload_json=_redact_json_text(self._open(str(row["payload_json"]))),
                )
                connection.execute(
                    "UPDATE checkpoints SET publication = 'quarantined' WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                )
                quarantined.append(checkpoint_id)
                mutated = True

            broken = self._quarantine_corrupt_checkpoints(connection)
            if broken:
                quarantined.extend(broken)
                mutated = True
                notes.append(
                    "published checkpoints failed payload verification and were quarantined"
                )

            approval_rows = connection.execute(
                "SELECT approval_id FROM approval_events WHERE expired = 0"
            ).fetchall()
            if approval_rows:
                connection.execute("UPDATE approval_events SET expired = 1 WHERE expired = 0")
                revoked = [str(row["approval_id"]) for row in approval_rows]
                mutated = True
                notes.append(
                    "approvals were revoked on recovery and are not reusable credentials"
                )

            active_goal_ids: set[str] = set()
            for goal in self._list_goals_on(connection):
                metadata = _redacted_mapping(goal.metadata)
                changed = metadata != goal.metadata
                if changed:
                    goal.metadata = metadata
                if goal.status == GoalStatus.ACTIVE:
                    active_goal_ids.add(goal.id)
                if changed:
                    self._write_goal(connection, goal)
                    mutated = True
                    notes.append(f"goal {goal.id} had sensitive metadata redacted")

            for task in self._list_tasks_on(connection):
                target: TaskState | None = None
                reason = ""
                if task.state in UNSAFE_RECOVERY_STATES:
                    target = TaskState.INTERRUPTED
                    reason = (
                        "recovered after incomplete execution; approval tokens are not restored"
                    )
                elif task.state == TaskState.APPROVED_IF_REQUIRED:
                    target = TaskState.WAITING_FOR_USER
                    reason = "approval does not survive restart and must be requested again"
                elif task.goal_id in active_goal_ids and task.state not in _STABLE_TASK_STATES:
                    target = TaskState.INTERRUPTED
                    reason = "goal was active when the process stopped"
                if target is not None and target != task.state:
                    self._transition_on(connection, task, target, reason)
                    mutated = True

            for goal in self._list_goals_on(connection):
                if goal.id not in active_goal_ids and goal.status != GoalStatus.ACTIVE:
                    continue
                goal_task = self._get_task_by_goal_on(connection, goal.id)
                if goal_task is not None and goal_task.state == TaskState.WAITING_FOR_USER:
                    goal.status = GoalStatus.WAITING_FOR_USER
                    goal.error = "approval does not survive restart and must be requested again"
                else:
                    goal.status = GoalStatus.INTERRUPTED
                    goal.error = (
                        "recovered after process stop; execution was not resumed "
                        "and approvals were not restored"
                    )
                goal.updated_at = _now()
                self._write_goal(connection, goal)
                interrupted.append(goal.id)
                mutated = True

            for context in self._list_contexts_on(connection):
                redacted_items = []
                changed = False
                for item in context.items:
                    if is_sensitive_key(item.key):
                        redacted: object = "[redacted]"
                    else:
                        redacted = redact_value(item.value)
                    if canonical_json(redacted) != canonical_json(item.value):
                        item.value = redacted
                        changed = True
                    redacted_items.append(item)
                if changed:
                    context.items = redacted_items
                    context.updated_at = _now()
                    self._write_context(connection, context)
                    mutated = True
                    notes.append(
                        f"context for goal {context.goal_id} had sensitive values redacted"
                    )

            integrity_ok = self._chain_ok(connection) and not broken

        if mutated:
            self.publish_checkpoint(reason="post_recovery", kernel_id="recovery")
            notes.append("published a post-recovery checkpoint of the normalized journal")

        if not integrity_ok:
            notes.append(
                "checkpoint hash chain did not verify; live rows were kept and "
                "automatic rollback was not performed"
            )

        return RecoveryReport(
            schema_version=version,
            interrupted_goal_ids=interrupted,
            revoked_approval_ids=revoked,
            quarantined_ids=quarantined,
            integrity_ok=integrity_ok,
            mutated=mutated,
            notes=notes,
        )

    def list_sessions(self) -> list[tuple[str, str]]:
        """Return persisted session ids and user ids."""
        self.migrate()
        with self._read() as connection:
            rows = connection.execute(
                "SELECT session_id, user_id FROM sessions ORDER BY created_at ASC"
            ).fetchall()
        return [(str(row["session_id"]), str(row["user_id"])) for row in rows]

    def ensure_session(self, session_id: str, user_id: str = "local") -> None:
        """Record a session id if it is not already present."""
        self._ensure_lock()
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, user_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id, user_id, _now().isoformat()),
            )

    def upsert_goal(self, goal: Goal) -> Goal:
        """Persist a goal after redacting sensitive metadata."""
        stored = goal.model_copy(deep=True)
        stored.metadata = _redacted_mapping(stored.metadata)
        self._ensure_lock()
        with self._transaction() as connection:
            self._write_goal(connection, stored)
        return stored

    def list_goals(self) -> list[Goal]:
        """Return persisted goals in creation order."""
        self.migrate()
        with self._read() as connection:
            return self._list_goals_on(connection)

    def get_goal(self, goal_id: str) -> Goal | None:
        """Return one persisted goal."""
        self.migrate()
        with self._read() as connection:
            return self._get_goal_on(connection, goal_id)

    def delete_goal(self, goal_id: str, reason: str) -> bool:
        """Delete live goal, context, and task rows.

        Published checkpoints are retained. The tombstone records the id and
        reason, not the objective text.
        """
        self._ensure_lock()
        with self._transaction() as connection:
            goal = self._get_goal_on(connection, goal_id)
            if goal is None:
                return False
            task = self._get_task_by_goal_on(connection, goal_id)
            connection.execute("DELETE FROM goals WHERE goal_id = ?", (goal_id,))
            connection.execute("DELETE FROM contexts WHERE goal_id = ?", (goal_id,))
            if task is not None:
                connection.execute("DELETE FROM task_runs WHERE task_id = ?", (task.task_id,))
            self._quarantine_on(
                connection,
                kind="deletion_tombstone",
                reason=reason,
                payload_json=canonical_json(
                    {"goal_id": goal_id, "deleted_at": _now().isoformat()}
                ),
            )
        return True

    def upsert_context(self, context: WorkingContext) -> WorkingContext:
        """Replace the stored working context for a goal."""
        stored = context.model_copy(deep=True)
        for item in stored.items:
            if is_sensitive_key(item.key):
                item.value = "[redacted]"
            else:
                item.value = redact_value(item.value)
        self._ensure_lock()
        with self._transaction() as connection:
            self._write_context(connection, stored)
        return stored

    def list_contexts(self) -> list[WorkingContext]:
        """Return persisted working contexts."""
        self.migrate()
        with self._read() as connection:
            return self._list_contexts_on(connection)

    def transition_task(self, goal: Goal, to_state: TaskState, reason: str) -> TaskRun:
        """Create or advance the task run for a goal."""
        self._ensure_lock()
        with self._transaction() as connection:
            current = self._get_task_by_goal_on(connection, goal.id)
            if current is None:
                current = self._insert_task(
                    connection,
                    goal,
                    TaskState.CREATED,
                    reason if to_state is TaskState.CREATED else "goal created",
                )
                if to_state is TaskState.CREATED:
                    return current
            return self._transition_on(connection, current, to_state, reason)

    def get_task_by_goal(self, goal_id: str) -> TaskRun | None:
        """Return the task run for a goal, if one exists."""
        self.migrate()
        with self._read() as connection:
            return self._get_task_by_goal_on(connection, goal_id)

    def list_tasks(self) -> list[TaskRun]:
        """Return task runs in creation order."""
        self.migrate()
        with self._read() as connection:
            return self._list_tasks_on(connection)

    def list_transitions(self, task_id: str | None = None) -> list[dict[str, Any]]:
        """Return append-only transition records."""
        self.migrate()
        with self._read() as connection:
            if task_id is None:
                rows = connection.execute(
                    """
                    SELECT transition_id, task_id, from_state, to_state, reason, created_at
                    FROM task_transitions
                    ORDER BY created_at ASC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT transition_id, task_id, from_state, to_state, reason, created_at
                    FROM task_transitions
                    WHERE task_id = ?
                    ORDER BY created_at ASC
                    """,
                    (task_id,),
                ).fetchall()
        return [
            {
                "transition_id": str(row["transition_id"]),
                "task_id": str(row["task_id"]),
                "from_state": None if row["from_state"] is None else str(row["from_state"]),
                "to_state": str(row["to_state"]),
                "reason": self._open(str(row["reason"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def update_task_budget(self, goal_id: str, budget: dict[str, Any]) -> None:
        """Store the latest budget snapshot on a task run."""
        self._ensure_lock()
        with self._transaction() as connection:
            task = self._get_task_by_goal_on(connection, goal_id)
            if task is None:
                return
            task.budget = _redacted_mapping(budget)
            task.updated_at = _now()
            self._write_task(connection, task)

    def publish_checkpoint(
        self,
        *,
        reason: str,
        kernel_id: str,
        parent_checkpoint_id: str | None = None,
    ) -> Checkpoint:
        """Publish a hash-linked snapshot in one transaction.

        A crash before commit leaves no draft row. Drafts committed by a
        partial writer are quarantined on recovery and are not authoritative.
        """
        self._ensure_lock()
        with self._transaction() as connection:
            payload = self._snapshot_on(connection)
            payload_json = canonical_json(payload)
            digest = sha256_text(payload_json)
            previous = self._latest_published_on(connection)
            previous_hash = GENESIS_HASH if previous is None else previous.payload_sha256
            parent_id = parent_checkpoint_id
            if parent_id is None and previous is not None:
                parent_id = previous.checkpoint_id
            checkpoint = Checkpoint(
                checkpoint_id=str(uuid4()),
                parent_checkpoint_id=parent_id,
                schema_version=SCHEMA_VERSION,
                reason=reason,
                payload_sha256=digest,
                previous_hash=previous_hash,
                publication="draft",
                created_at=_now(),
                kernel_id=kernel_id,
                payload_json=payload_json,
            )
            if sha256_text(payload_json) != checkpoint.payload_sha256:
                raise ContinuityIntegrityError("checkpoint hash did not match its payload")
            checkpoint.publication = "published"
            self._insert_checkpoint(connection, checkpoint)
        if self.checkpoint_witness is not None:
            self.checkpoint_witness(checkpoint)
        return checkpoint

    def list_checkpoints(self, *, publication: str | None = "published") -> list[Checkpoint]:
        """List checkpoints, omitting payload bodies."""
        self.migrate()
        with self._read() as connection:
            if publication is None:
                rows = connection.execute(
                    """
                    SELECT * FROM checkpoints
                    ORDER BY created_at ASC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM checkpoints
                    WHERE publication = ?
                    ORDER BY created_at ASC
                    """,
                    (publication,),
                ).fetchall()
        return [self._checkpoint_from_row(row, include_payload=False) for row in rows]

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Return one checkpoint, including its payload."""
        self.migrate()
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).fetchone()
        if row is None:
            return None
        return self._checkpoint_from_row(row, include_payload=True)

    def verify_checkpoint(self, checkpoint_id: str) -> bool:
        """Return whether a published checkpoint payload matches its digest."""
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None or checkpoint.publication != "published":
            return False
        if checkpoint.payload_json is None:
            return False
        return sha256_text(checkpoint.payload_json) == checkpoint.payload_sha256

    def verify_chain(self) -> bool:
        """Return whether every published checkpoint links to the previous digest."""
        self.migrate()
        with self._read() as connection:
            return self._chain_ok(connection)

    def rollback_to(self, checkpoint_id: str, *, kernel_id: str = "rollback") -> Checkpoint:
        """Restore live rows from a verified checkpoint, then publish that restoration.

        In-flight and approved states inside the snapshot are normalized so a
        rollback cannot resume execution or revive an approval.
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None or checkpoint.publication != "published":
            raise ContinuityIntegrityError(
                f"checkpoint is not a published snapshot: {checkpoint_id}"
            )
        if not self.verify_checkpoint(checkpoint_id):
            raise ContinuityIntegrityError(
                f"checkpoint failed integrity verification: {checkpoint_id}"
            )
        if checkpoint.payload_json is None:
            raise ContinuityIntegrityError("checkpoint payload is missing")
        payload = json_object(checkpoint.payload_json)
        self._ensure_lock()
        with self._transaction() as connection:
            connection.execute("DELETE FROM goals")
            connection.execute("DELETE FROM contexts")
            connection.execute("DELETE FROM task_runs")
            for item in _json_list(payload.get("goals")):
                goal = Goal.model_validate(_as_mapping(item))
                goal.metadata = _redacted_mapping(goal.metadata)
                self._write_goal(connection, goal)
            for item in _json_list(payload.get("contexts")):
                context = WorkingContext.model_validate(_as_mapping(item))
                for entry in context.items:
                    if is_sensitive_key(entry.key):
                        entry.value = "[redacted]"
                    else:
                        entry.value = redact_value(entry.value)
                self._write_context(connection, context)
            for item in _json_list(payload.get("task_runs")):
                task = TaskRun.model_validate(_as_mapping(item))
                self._write_task(connection, task)
            self._normalize_restored_work(connection)
        return self.publish_checkpoint(
            reason="rollback",
            kernel_id=kernel_id,
            parent_checkpoint_id=checkpoint_id,
        )

    def create_branch(
        self,
        parent_checkpoint_id: str,
        reason: str,
        model_configuration: dict[str, Any],
        tool_policy: dict[str, Any],
    ) -> WorkBranch:
        """Record a branch at a verified checkpoint without copying secrets."""
        if not self.verify_checkpoint(parent_checkpoint_id):
            raise ContinuityIntegrityError(
                f"cannot branch from an unverified checkpoint: {parent_checkpoint_id}"
            )
        checkpoint = self.get_checkpoint(parent_checkpoint_id)
        if checkpoint is None or checkpoint.payload_json is None:
            raise ContinuityIntegrityError(f"missing checkpoint payload: {parent_checkpoint_id}")
        payload = json_object(checkpoint.payload_json)
        project_hash = sha256_text(canonical_json(payload.get("goals", [])))
        branch = WorkBranch(
            branch_id=str(uuid4()),
            parent_checkpoint_id=parent_checkpoint_id,
            fork_reason=reason,
            memory_snapshot_hash=checkpoint.payload_sha256,
            project_snapshot_hash=project_hash,
            model_configuration=_redacted_mapping(model_configuration),
            tool_policy=_redacted_mapping(tool_policy),
            created_at=_now(),
        )
        self._ensure_lock()
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO branches (
                    branch_id, parent_checkpoint_id, fork_reason,
                    memory_snapshot_hash, project_snapshot_hash,
                    model_configuration_json, tool_policy_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch.branch_id,
                    branch.parent_checkpoint_id,
                    self._seal(branch.fork_reason),
                    branch.memory_snapshot_hash,
                    branch.project_snapshot_hash,
                    self._seal(canonical_json(branch.model_configuration)),
                    self._seal(canonical_json(branch.tool_policy)),
                    branch.created_at.isoformat(),
                ),
            )
        return branch

    def list_branches(self) -> list[WorkBranch]:
        """Return recorded work branches."""
        self.migrate()
        with self._read() as connection:
            rows = connection.execute(
                "SELECT * FROM branches ORDER BY created_at ASC"
            ).fetchall()
        branches: list[WorkBranch] = []
        for row in rows:
            branches.append(
                WorkBranch(
                    branch_id=str(row["branch_id"]),
                    parent_checkpoint_id=str(row["parent_checkpoint_id"]),
                    fork_reason=self._open(str(row["fork_reason"])),
                    memory_snapshot_hash=str(row["memory_snapshot_hash"]),
                    project_snapshot_hash=str(row["project_snapshot_hash"]),
                    model_configuration=_as_mapping(
                        json_object(self._open(str(row["model_configuration_json"])))
                    ),
                    tool_policy=_as_mapping(
                        json_object(self._open(str(row["tool_policy_json"])))
                    ),
                    created_at=datetime.fromisoformat(str(row["created_at"])),
                )
            )
        return branches

    def get_branch(self, branch_id: str) -> WorkBranch | None:
        """Return one work branch."""
        for branch in self.list_branches():
            if branch.branch_id == branch_id:
                return branch
        return None

    def record_approval_event(
        self,
        *,
        task_id: str,
        goal_id: str,
        action_fingerprint: str,
        approver: str,
        decision: str,
        process_nonce: str,
    ) -> ApprovalEvent:
        """Append a non-reusable approval audit event."""
        event = ApprovalEvent(
            approval_id=str(uuid4()),
            task_id=task_id,
            goal_id=goal_id,
            action_fingerprint=action_fingerprint,
            approver=approver,
            decision=decision,
            process_nonce=process_nonce,
            reusable=False,
            expired=False,
            created_at=_now(),
        )
        self._ensure_lock()
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO approval_events (
                    approval_id, task_id, goal_id, action_fingerprint, approver,
                    decision, process_nonce, reusable, expired, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                """,
                (
                    event.approval_id,
                    event.task_id,
                    event.goal_id,
                    event.action_fingerprint,
                    event.approver,
                    event.decision,
                    event.process_nonce,
                    event.created_at.isoformat(),
                ),
            )
        return event

    def list_approval_events(self) -> list[ApprovalEvent]:
        """Return approval audit events. None of them authorize execution."""
        self.migrate()
        with self._read() as connection:
            rows = connection.execute(
                "SELECT * FROM approval_events ORDER BY created_at ASC"
            ).fetchall()
        return [
            ApprovalEvent(
                approval_id=str(row["approval_id"]),
                task_id=str(row["task_id"]),
                goal_id=str(row["goal_id"]),
                action_fingerprint=str(row["action_fingerprint"]),
                approver=str(row["approver"]),
                decision=str(row["decision"]),
                process_nonce=str(row["process_nonce"]),
                reusable=bool(row["reusable"]),
                expired=bool(row["expired"]),
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
            for row in rows
        ]

    def list_quarantine(self) -> list[QuarantineRecord]:
        """Return dead-letter and tombstone records."""
        self.migrate()
        with self._read() as connection:
            rows = connection.execute(
                "SELECT * FROM quarantine ORDER BY created_at ASC"
            ).fetchall()
        return [
            QuarantineRecord(
                record_id=str(row["record_id"]),
                kind=str(row["kind"]),
                reason=str(row["reason"]),
                payload_json=self._open(str(row["payload_json"])),
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
            for row in rows
        ]

    def export_audit_bundle(self) -> dict[str, Any]:
        """Export continuity metadata for operator inspection.

        The bundle includes checkpoint digests, transitions, quarantine notes,
        and expired approval events. It is not a claim of cryptographic immutability.
        """
        self.migrate()
        checkpoints = []
        for checkpoint in self.list_checkpoints(publication=None):
            checkpoints.append(
                {
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
                    "reason": checkpoint.reason,
                    "payload_sha256": checkpoint.payload_sha256,
                    "previous_hash": checkpoint.previous_hash,
                    "publication": checkpoint.publication,
                    "created_at": checkpoint.created_at.isoformat(),
                    "kernel_id": checkpoint.kernel_id,
                    "self_hash_ok": (
                        checkpoint.publication == "published"
                        and self.verify_checkpoint(checkpoint.checkpoint_id)
                    ),
                }
            )
        approvals = [
            {
                "approval_id": event.approval_id,
                "task_id": event.task_id,
                "goal_id": event.goal_id,
                "decision": event.decision,
                "approver": event.approver,
                "reusable": False,
                "expired": event.expired,
                "created_at": event.created_at.isoformat(),
            }
            for event in self.list_approval_events()
        ]
        return {
            "schema_version": self.schema_version(),
            "backend": "sqlite",
            "local_first": True,
            "network": "none",
            "integrity_ok": self.verify_chain(),
            "cryptographic_immutability": False,
            "checkpoints": checkpoints,
            "transitions": self.list_transitions(),
            "quarantine": [record.model_dump(mode="json") for record in self.list_quarantine()],
            "approval_events": approvals,
            "branches": [branch.model_dump(mode="json") for branch in self.list_branches()],
        }

    def status_summary(self, recovery: RecoveryReport | None = None) -> dict[str, Any]:
        """Return operator status without inventing durability the store lacks."""
        if not self.db_path.exists():
            return {
                "capability": "cognitive_continuity",
                "status": "unavailable",
                "durable": False,
                "reason": "Continuity journal file does not exist.",
            }
        try:
            version = self.schema_version()
            published = self.list_checkpoints()
            integrity_ok = self.verify_chain()
        except DataKeyError as exc:
            return {
                "capability": "cognitive_continuity",
                "status": "degraded",
                "durable": True,
                "backend": "sqlite",
                "local_first": True,
                "network": "none",
                "encrypted_at_rest": True,
                "cryptographic_immutability": False,
                "reason": str(exc),
                "integrity": "degraded",
                "db_path": str(self.db_path),
            }
        if recovery is not None and not recovery.integrity_ok:
            integrity_ok = False
        status = "available" if integrity_ok else "degraded"
        head = published[-1].checkpoint_id if published else None
        return {
            "capability": "cognitive_continuity",
            "status": status,
            "durable": True,
            "backend": "sqlite",
            "schema_version": version,
            "local_first": True,
            "network": "none",
            "encrypted_at_rest": self.cipher is not None,
            "cryptographic_immutability": False,
            "checkpoint_count": len(published),
            "published_head": head,
            "integrity": "verified" if integrity_ok else "degraded",
            "db_path": str(self.db_path),
            "recovery": recovery.model_dump(mode="json") if recovery is not None else None,
        }

    def _ensure_lock(self) -> None:
        if self._lock_held:
            return
        holder = ""
        if self.lock_path.exists():
            holder = self.lock_path.read_text(encoding="utf-8").strip()
            if holder == str(os.getpid()):
                self._lock_held = True
                return
            if holder and _pid_alive(holder):
                raise ContinuityLockedError(holder)
        self.lock_path.write_text(str(os.getpid()), encoding="utf-8")
        self._lock_held = True
        atexit.register(_release_lock_file, self.lock_path, os.getpid())

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _bootstrap(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

    def _schema_version(self, connection: sqlite3.Connection) -> int:
        row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        if row is None or row["version"] is None:
            return 0
        return int(row["version"])

    def _record_migration(self, connection: sqlite3.Connection, version: int, name: str) -> None:
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (version, name, _now().isoformat()),
        )

    def _write_goal(self, connection: sqlite3.Connection, goal: Goal) -> None:
        payload = self._seal(canonical_json(goal.model_dump(mode="json")))
        connection.execute(
            """
            INSERT INTO goals (goal_id, session_id, status, goal_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(goal_id) DO UPDATE SET
                session_id = excluded.session_id,
                status = excluded.status,
                goal_json = excluded.goal_json,
                updated_at = excluded.updated_at
            """,
            (
                goal.id,
                goal.session_id,
                goal.status.value,
                payload,
                goal.updated_at.isoformat(),
            ),
        )

    def _get_goal_on(self, connection: sqlite3.Connection, goal_id: str) -> Goal | None:
        row = connection.execute(
            "SELECT goal_json FROM goals WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()
        if row is None:
            return None
        return Goal.model_validate(json_object(self._open(str(row["goal_json"]))))

    def _list_goals_on(self, connection: sqlite3.Connection) -> list[Goal]:
        rows = connection.execute(
            "SELECT goal_json FROM goals ORDER BY updated_at ASC"
        ).fetchall()
        goals = [
            Goal.model_validate(json_object(self._open(str(row["goal_json"])))) for row in rows
        ]
        return sorted(goals, key=lambda goal: goal.created_at)

    def _write_context(self, connection: sqlite3.Connection, context: WorkingContext) -> None:
        connection.execute(
            """
            INSERT INTO contexts (goal_id, context_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(goal_id) DO UPDATE SET
                context_json = excluded.context_json,
                updated_at = excluded.updated_at
            """,
            (
                context.goal_id,
                self._seal(canonical_json(context.model_dump(mode="json"))),
                context.updated_at.isoformat(),
            ),
        )

    def _list_contexts_on(self, connection: sqlite3.Connection) -> list[WorkingContext]:
        rows = connection.execute("SELECT context_json FROM contexts").fetchall()
        return [
            WorkingContext.model_validate(json_object(self._open(str(row["context_json"]))))
            for row in rows
        ]

    def _insert_task(
        self,
        connection: sqlite3.Connection,
        goal: Goal,
        state: TaskState,
        reason: str,
    ) -> TaskRun:
        now = _now()
        task = TaskRun(
            task_id=str(uuid4()),
            goal_id=goal.id,
            session_id=goal.session_id,
            state=state,
            action_fingerprint=_action_fingerprint(goal),
            objective=goal.objective,
            created_at=now,
            updated_at=now,
            error=reason if state is not TaskState.CREATED else None,
        )
        self._write_task(connection, task)
        self._insert_transition(connection, task.task_id, None, state, reason)
        return task

    def _transition_on(
        self,
        connection: sqlite3.Connection,
        current: TaskRun,
        to_state: TaskState,
        reason: str,
    ) -> TaskRun:
        if current.state == to_state:
            return current
        validate_transition(current.state, to_state)
        updated = current.model_copy(
            update={
                "state": to_state,
                "updated_at": _now(),
                "error": reason,
            }
        )
        self._write_task(connection, updated)
        self._insert_transition(
            connection,
            current.task_id,
            current.state,
            to_state,
            reason,
        )
        return updated

    def _write_task(self, connection: sqlite3.Connection, task: TaskRun) -> None:
        connection.execute(
            """
            INSERT INTO task_runs (
                task_id, goal_id, state, action_fingerprint, task_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                goal_id = excluded.goal_id,
                state = excluded.state,
                action_fingerprint = excluded.action_fingerprint,
                task_json = excluded.task_json,
                updated_at = excluded.updated_at
            """,
            (
                task.task_id,
                task.goal_id,
                task.state.value,
                task.action_fingerprint,
                self._seal(canonical_json(task.model_dump(mode="json"))),
                task.updated_at.isoformat(),
            ),
        )

    def _get_task_by_goal_on(
        self,
        connection: sqlite3.Connection,
        goal_id: str,
    ) -> TaskRun | None:
        row = connection.execute(
            "SELECT task_json FROM task_runs WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()
        if row is None:
            return None
        return TaskRun.model_validate(json_object(self._open(str(row["task_json"]))))

    def _list_tasks_on(self, connection: sqlite3.Connection) -> list[TaskRun]:
        rows = connection.execute(
            "SELECT task_json FROM task_runs ORDER BY updated_at ASC"
        ).fetchall()
        tasks = [
            TaskRun.model_validate(json_object(self._open(str(row["task_json"])))) for row in rows
        ]
        return sorted(tasks, key=lambda task: task.created_at)

    def _insert_transition(
        self,
        connection: sqlite3.Connection,
        task_id: str,
        from_state: TaskState | None,
        to_state: TaskState,
        reason: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO task_transitions (
                transition_id, task_id, from_state, to_state, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                task_id,
                None if from_state is None else from_state.value,
                to_state.value,
                self._seal(reason),
                _now().isoformat(),
            ),
        )

    def _snapshot_on(self, connection: sqlite3.Connection) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "goals": [goal.model_dump(mode="json") for goal in self._list_goals_on(connection)],
            "contexts": [
                context.model_dump(mode="json") for context in self._list_contexts_on(connection)
            ],
            "task_runs": [task.model_dump(mode="json") for task in self._list_tasks_on(connection)],
        }

    def _latest_published_on(self, connection: sqlite3.Connection) -> Checkpoint | None:
        row = connection.execute(
            """
            SELECT * FROM checkpoints
            WHERE publication = 'published'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return self._checkpoint_from_row(row, include_payload=False)

    def _insert_checkpoint(self, connection: sqlite3.Connection, checkpoint: Checkpoint) -> None:
        if checkpoint.payload_json is None:
            raise ContinuityIntegrityError("cannot persist a checkpoint without a payload")
        connection.execute(
            """
            INSERT INTO checkpoints (
                checkpoint_id, parent_checkpoint_id, schema_version, reason,
                payload_json, payload_sha256, previous_hash, publication,
                created_at, kernel_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint.checkpoint_id,
                checkpoint.parent_checkpoint_id,
                checkpoint.schema_version,
                self._seal(checkpoint.reason),
                self._seal(checkpoint.payload_json),
                checkpoint.payload_sha256,
                checkpoint.previous_hash,
                checkpoint.publication,
                checkpoint.created_at.isoformat(),
                checkpoint.kernel_id,
            ),
        )

    def _checkpoint_from_row(self, row: sqlite3.Row, *, include_payload: bool) -> Checkpoint:
        return Checkpoint(
            checkpoint_id=str(row["checkpoint_id"]),
            parent_checkpoint_id=(
                None
                if row["parent_checkpoint_id"] is None
                else str(row["parent_checkpoint_id"])
            ),
            schema_version=int(row["schema_version"]),
            reason=self._open(str(row["reason"])),
            payload_sha256=str(row["payload_sha256"]),
            previous_hash=str(row["previous_hash"]),
            publication=str(row["publication"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            kernel_id=str(row["kernel_id"]),
            payload_json=(
                self._open(str(row["payload_json"])) if include_payload else None
            ),
        )

    def _published_rows(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return list(
            connection.execute(
                """
                SELECT * FROM checkpoints
                WHERE publication = 'published'
                ORDER BY created_at ASC
                """
            ).fetchall()
        )

    def _chain_ok(self, connection: sqlite3.Connection) -> bool:
        expected = GENESIS_HASH
        for row in self._published_rows(connection):
            payload_json = self._open(str(row["payload_json"]))
            digest = str(row["payload_sha256"])
            previous = str(row["previous_hash"])
            if previous != expected or sha256_text(payload_json) != digest:
                return False
            expected = digest
        return True

    def _quarantine_corrupt_checkpoints(self, connection: sqlite3.Connection) -> list[str]:
        broken: list[str] = []
        for row in self._published_rows(connection):
            payload_json = self._open(str(row["payload_json"]))
            digest = str(row["payload_sha256"])
            if sha256_text(payload_json) == digest:
                continue
            checkpoint_id = str(row["checkpoint_id"])
            self._quarantine_on(
                connection,
                kind="integrity_failure",
                reason="published checkpoint payload did not match its digest",
                payload_json=canonical_json(
                    {"checkpoint_id": checkpoint_id, "expected_sha256": digest}
                ),
            )
            connection.execute(
                "UPDATE checkpoints SET publication = 'quarantined' WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            broken.append(checkpoint_id)
        return broken

    def _quarantine_on(
        self,
        connection: sqlite3.Connection,
        *,
        kind: str,
        reason: str,
        payload_json: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO quarantine (record_id, kind, reason, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid4()), kind, reason, self._seal(payload_json), _now().isoformat()),
        )

    def _normalize_restored_work(self, connection: sqlite3.Connection) -> None:
        """Stop restored in-flight work and revoke surviving approval states."""
        for task in self._list_tasks_on(connection):
            if task.state in UNSAFE_RECOVERY_STATES:
                self._transition_on(
                    connection,
                    task,
                    TaskState.INTERRUPTED,
                    "rollback does not resume in-flight execution",
                )
            elif task.state == TaskState.APPROVED_IF_REQUIRED:
                self._transition_on(
                    connection,
                    task,
                    TaskState.WAITING_FOR_USER,
                    "rollback does not restore approvals",
                )
        for goal in self._list_goals_on(connection):
            goal_task = self._get_task_by_goal_on(connection, goal.id)
            if goal_task is not None and goal_task.state == TaskState.WAITING_FOR_USER:
                if goal.status != GoalStatus.WAITING_FOR_USER:
                    goal.status = GoalStatus.WAITING_FOR_USER
                    goal.error = "rollback does not restore approvals"
                    goal.updated_at = _now()
                    self._write_goal(connection, goal)
                continue
            if goal.status == GoalStatus.ACTIVE or (
                goal_task is not None and goal_task.state == TaskState.INTERRUPTED
            ):
                if goal.status != GoalStatus.INTERRUPTED:
                    goal.status = GoalStatus.INTERRUPTED
                    goal.error = "rollback restored this goal as interrupted"
                    goal.updated_at = _now()
                    self._write_goal(connection, goal)


_STABLE_TASK_STATES: frozenset[TaskState] = frozenset(
    {
        TaskState.INTERRUPTED,
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.ROLLED_BACK,
        TaskState.QUARANTINED,
        TaskState.WAITING_FOR_USER,
    }
)


def _reseal_column(
    connection: sqlite3.Connection,
    cipher: FieldCipher,
    table: str,
    key_column: str,
    value_column: str,
) -> int:
    rows = connection.execute(f"SELECT {key_column} AS pk, {value_column} AS value FROM {table}")
    changed = 0
    for row in rows:
        sealed = seal_if_plain(cipher, str(row["value"]))
        if sealed is None:
            continue
        connection.execute(
            f"UPDATE {table} SET {value_column} = ? WHERE {key_column} = ?",
            (sealed, row["pk"]),
        )
        changed += 1
    return changed


def _execute_sql_script(connection: sqlite3.Connection, script: str) -> None:
    """Execute semicolon-separated SQL without the implicit commit of executescript."""
    for statement in script.split(";"):
        sql = statement.strip()
        if sql:
            connection.execute(sql)


def _redact_json_text(payload_json: str) -> str:
    try:
        parsed: object = json.loads(payload_json)
    except json.JSONDecodeError:
        return canonical_json({"unparsed_payload": "[redacted]"})
    return canonical_json(redact_value(parsed))


def _action_fingerprint(goal: Goal) -> str:
    return sha256_text(
        canonical_json(
            {
                "capabilities": sorted(goal.capabilities),
                "goal_id": goal.id,
                "objective": goal.objective,
            }
        )
    )


def _json_list(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ContinuityIntegrityError("checkpoint payload list was not a list")
    return list(value)
