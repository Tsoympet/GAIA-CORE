"""AES-GCM field encryption for local SQLite stores.

The cipher seals individual text fields. It does not make the hash chain
cryptographically immutable. A privileged local writer who also has the key
can still recompute hashes. Without the key, sealed fields do not open.
"""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SEAL_PREFIX = "gaia-enc-v1:"
_KEY_BYTES = 32
_NONCE_BYTES = 12
_ASSOCIATED_DATA = b"gaia-field-v1"


class DataKeyError(ValueError):
    """Raised when a data key is missing, malformed, or cannot open a field."""


class FieldCipher:
    """Seal and open UTF-8 text fields with a 32-byte key."""

    def __init__(self, key: bytes) -> None:
        if len(key) != _KEY_BYTES:
            raise DataKeyError("data key must be 32 bytes")
        self._aesgcm = AESGCM(key)

    def seal(self, plaintext: str) -> str:
        """Return a self-describing ciphertext. The same text seals differently each call."""
        nonce = secrets.token_bytes(_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), _ASSOCIATED_DATA)
        encoded = base64.b64encode(nonce + ciphertext).decode("ascii")
        return SEAL_PREFIX + encoded

    def open(self, stored: str) -> str:
        """Open one sealed field."""
        if not is_sealed(stored):
            raise DataKeyError("field is not sealed")
        try:
            raw = base64.b64decode(stored[len(SEAL_PREFIX) :], validate=True)
            plaintext = self._aesgcm.decrypt(
                raw[:_NONCE_BYTES],
                raw[_NONCE_BYTES :],
                _ASSOCIATED_DATA,
            )
        except Exception as exc:
            raise DataKeyError("data key cannot open this field") from exc
        return plaintext.decode("utf-8")


def is_sealed(stored: str) -> bool:
    """Return whether a stored field uses the field-cipher prefix."""
    return stored.startswith(SEAL_PREFIX)


def seal_field(cipher: FieldCipher | None, plaintext: str) -> str:
    """Seal plaintext when a cipher is configured."""
    if cipher is None:
        return plaintext
    return cipher.seal(plaintext)


def open_field(cipher: FieldCipher | None, stored: str) -> str:
    """Return plaintext. Unsealed legacy values pass through when no cipher is required."""
    if not is_sealed(stored):
        return stored
    if cipher is None:
        raise DataKeyError("encrypted field requires a data key")
    return cipher.open(stored)


def seal_if_plain(cipher: FieldCipher | None, stored: str) -> str | None:
    """Return a sealed value when ``stored`` is still plaintext."""
    if cipher is None or is_sealed(stored):
        return None
    return cipher.seal(stored)


def read_data_key(path: Path) -> bytes:
    """Read a base64-encoded 32-byte key. The key bytes are not logged."""
    if not path.exists():
        raise DataKeyError(f"data key file does not exist: {path}")
    encoded = path.read_text(encoding="utf-8").strip()
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise DataKeyError("data key file is not valid base64") from exc
    if len(key) != _KEY_BYTES:
        raise DataKeyError("data key must be 32 bytes")
    return key


def write_data_key(path: Path) -> None:
    """Create a new key file. An existing file is left untouched."""
    if path.exists():
        raise DataKeyError(f"data key file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    key = AESGCM.generate_key(bit_length=256)
    path.write_text(base64.b64encode(key).decode("ascii") + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
