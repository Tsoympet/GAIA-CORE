"""Canonical JSON and content hashing for continuity records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def canonical_json(value: object) -> str:
    """Serialize a value with stable key order for hashing and storage."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object and reject other JSON types."""
    loaded: object = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("expected a JSON object")
    parsed: dict[str, Any] = {}
    for key, value in loaded.items():
        if not isinstance(key, str):
            raise ValueError("expected string JSON keys")
        parsed[key] = value
    return parsed
