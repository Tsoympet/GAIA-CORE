"""Bind published continuity checkpoints to evidence without copying payloads."""

from __future__ import annotations

from gaia.continuity.records import Checkpoint
from gaia.evidence.codec import canonical_json
from gaia.organism.guards import redact_assignments

CHECKPOINT_ORIGIN = "continuity-checkpoint"
CHECKPOINT_PRODUCER = "cognitive_continuity"


def checkpoint_evidence_content(checkpoint: Checkpoint) -> str:
    """Return the digest citation stored as evidence.

    The continuity payload, including objectives and context, is not included.
    """
    if checkpoint.publication != "published":
        raise ValueError("only published checkpoints can be cited as evidence")
    return canonical_json(
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
            "schema_version": checkpoint.schema_version,
            "reason": redact_assignments(checkpoint.reason),
            "payload_sha256": checkpoint.payload_sha256,
            "previous_hash": checkpoint.previous_hash,
            "publication": checkpoint.publication,
            "created_at": checkpoint.created_at.isoformat(),
            "kernel_id": checkpoint.kernel_id,
        }
    )
