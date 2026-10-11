"""AES-GCM field encryption for continuity, evidence, and organism stores."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typer.testing import CliRunner

from gaia.cli import app
from gaia.continuity.store import ContinuityStore
from gaia.evidence.ledger import EvidenceLedger
from gaia.kernel.goal_manager import Goal
from gaia.organism.organism import MemoryOrganism
from gaia.security.field_cipher import DataKeyError, FieldCipher, is_sealed


def _key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def test_same_plaintext_seals_differently() -> None:
    cipher = FieldCipher(_key())
    first = cipher.seal("hydrostatic")
    second = cipher.seal("hydrostatic")
    assert first != second
    assert cipher.open(first) == "hydrostatic"
    assert is_sealed(first)


def test_evidence_and_memory_hide_plaintext_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "organism.sqlite3"
    secret = "token=super-secret observation"
    cipher = FieldCipher(_key())
    organism = MemoryOrganism(path, cipher=cipher)
    evidence = organism.evidence.append(
        source="user",
        origin="note",
        content=secret,
        producer="operator",
    )
    memory = organism.record_episodic(evidence.evidence_id, owner_id="local")
    raw = path.read_bytes()
    assert b"super-secret" not in raw
    assert organism.evidence.verify_chain() is True

    reloaded = MemoryOrganism(path, cipher=cipher)
    restored = reloaded.evidence.get(evidence.evidence_id)
    assert restored is not None
    assert restored.content_text == secret
    loaded_memory = reloaded.get(memory.memory_id)
    assert loaded_memory is not None
    assert loaded_memory.content == secret
    assert reloaded.evidence.verify_chain() is True
    assert reloaded.status()["encrypted_at_rest"] is True

    locked = MemoryOrganism(path)
    assert locked.status()["status"] == "degraded"
    assert locked.status()["encrypted_at_rest"] is True
    wrong = MemoryOrganism(path, cipher=FieldCipher(_key()))
    assert wrong.status()["status"] == "degraded"
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT content_text FROM evidence_bodies WHERE evidence_id = ?",
            (evidence.evidence_id,),
        ).fetchone()
    assert row is not None
    assert is_sealed(str(row[0]))


def test_adding_a_key_seals_existing_plaintext_and_keeps_the_chain(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    ledger = EvidenceLedger(path)
    record = ledger.append(
        source="user",
        origin="note",
        content="visible-once freeboard",
        producer="operator",
    )
    assert b"visible-once" in path.read_bytes()
    cipher = FieldCipher(_key())
    sealed = EvidenceLedger(path, cipher=cipher)
    assert b"visible-once" not in path.read_bytes()
    restored = sealed.get(record.evidence_id)
    assert restored is not None
    assert restored.content_text == "visible-once freeboard"
    assert sealed.verify_chain() is True
    assert sealed.status()["cryptographic_immutability"] is False


def test_continuity_digest_survives_sealing(tmp_path: Path) -> None:
    path = tmp_path / "continuity.sqlite3"
    store = ContinuityStore(path)
    goal = Goal(objective="Move token=super-secret ballast", session_id="session-seal")
    store.upsert_goal(goal)
    checkpoint = store.publish_checkpoint(reason="operator", kernel_id="kernel-1")
    assert store.verify_chain() is True

    cipher = FieldCipher(_key())
    sealed = ContinuityStore(path, cipher=cipher)
    assert b"super-secret" not in path.read_bytes()
    assert sealed.verify_chain() is True
    loaded = sealed.get_goal(goal.id)
    assert loaded is not None
    assert loaded.objective == goal.objective
    opened = sealed.get_checkpoint(checkpoint.checkpoint_id)
    assert opened is not None
    assert opened.payload_sha256 == checkpoint.payload_sha256
    assert opened.payload_json is not None
    assert "super-secret" in opened.payload_json
    assert sealed.status_summary()["encrypted_at_rest"] is True
    assert sealed.status_summary()["cryptographic_immutability"] is False

    with pytest.raises(DataKeyError):
        ContinuityStore(path).get_goal(goal.id)
    wrong = ContinuityStore(path, cipher=FieldCipher(_key()))
    assert wrong.status_summary()["status"] == "degraded"
    with sqlite3.connect(path) as connection:
        publication = connection.execute(
            "SELECT publication FROM checkpoints WHERE checkpoint_id = ?",
            (checkpoint.checkpoint_id,),
        ).fetchone()
    assert publication is not None
    assert publication[0] == "published"


def test_cli_data_key_creates_a_file_and_refuses_to_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "data.key"
    runner = CliRunner()
    created = runner.invoke(app, ["data-key", "--path", str(path)])
    assert created.exit_code == 0
    assert path.stat().st_mode & 0o777 == 0o600
    again = runner.invoke(app, ["data-key", "--path", str(path)])
    assert again.exit_code == 1
    assert "already exists" in again.stdout
