"""Cognitive continuity: durable task state, checkpoints, and recovery."""

from __future__ import annotations

import importlib

__all__ = [
    "LIMITATIONS",
    "SCHEMA_VERSION",
    "ApprovalEvent",
    "Checkpoint",
    "ContinuityIntegrityError",
    "ContinuityJournal",
    "ContinuityLockedError",
    "ContinuityStore",
    "RecoveryReport",
    "TaskRun",
    "TaskState",
    "TaskTransitionError",
    "WorkBranch",
    "canonical_json",
    "is_sensitive_key",
    "redact_value",
    "sha256_text",
    "validate_transition",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "LIMITATIONS": ("gaia.continuity.journal", "LIMITATIONS"),
    "SCHEMA_VERSION": ("gaia.continuity.schema", "SCHEMA_VERSION"),
    "ApprovalEvent": ("gaia.continuity.records", "ApprovalEvent"),
    "Checkpoint": ("gaia.continuity.records", "Checkpoint"),
    "ContinuityIntegrityError": ("gaia.continuity.errors", "ContinuityIntegrityError"),
    "ContinuityJournal": ("gaia.continuity.journal", "ContinuityJournal"),
    "ContinuityLockedError": ("gaia.continuity.errors", "ContinuityLockedError"),
    "ContinuityStore": ("gaia.continuity.store", "ContinuityStore"),
    "RecoveryReport": ("gaia.continuity.records", "RecoveryReport"),
    "TaskRun": ("gaia.continuity.records", "TaskRun"),
    "TaskState": ("gaia.continuity.task_state", "TaskState"),
    "TaskTransitionError": ("gaia.continuity.task_state", "TaskTransitionError"),
    "WorkBranch": ("gaia.continuity.records", "WorkBranch"),
    "canonical_json": ("gaia.continuity.codec", "canonical_json"),
    "is_sensitive_key": ("gaia.continuity.redaction", "is_sensitive_key"),
    "redact_value": ("gaia.continuity.redaction", "redact_value"),
    "sha256_text": ("gaia.continuity.codec", "sha256_text"),
    "validate_transition": ("gaia.continuity.task_state", "validate_transition"),
}


def __getattr__(name: str) -> object:
    """Load continuity exports without importing the kernel during package init."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    module = importlib.import_module(module_name)
    value = getattr(module, attribute)
    globals()[name] = value
    return value
