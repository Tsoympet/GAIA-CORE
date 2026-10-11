"""Redaction of credentials and approval material before persistence."""

from __future__ import annotations

from typing import Any

_SENSITIVE_SEGMENTS: frozenset[str] = frozenset(
    {
        "token",
        "secret",
        "password",
        "passwd",
        "credential",
        "credentials",
        "authorization",
        "bearer",
        "cookie",
        "apikey",
    }
)


def is_sensitive_key(key: str) -> bool:
    """Return whether a mapping key may carry a secret or approval token."""
    normalized = key.strip().lower().replace("-", "_")
    segments = [part for part in normalized.split("_") if part]
    if any(part in _SENSITIVE_SEGMENTS for part in segments):
        return True
    if "api" in segments and "key" in segments:
        return True
    return "private" in segments and "key" in segments


def redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    """Redact a string-keyed mapping and drop non-string keys."""
    redacted = redact_value(value)
    if not isinstance(redacted, dict):
        return {}
    mapped: dict[str, Any] = {}
    for key, item in redacted.items():
        if isinstance(key, str):
            mapped[key] = item
    return mapped


def redact_value(value: object) -> object:
    """Replace sensitive mapping entries with a stable redaction marker."""
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if is_sensitive_key(key):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value
