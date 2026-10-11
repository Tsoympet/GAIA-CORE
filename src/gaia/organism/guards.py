"""Guards that keep untrusted text out of authoritative knowledge."""

from __future__ import annotations

import re

_INSTRUCTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous",
    "you are now",
    "system prompt",
    "developer message",
    "override the security policy",
    "grant yourself",
    "disregard the rules",
)

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|authorization)\b\s*[:=]\s*\S+"
)

UNTRUSTED_SOURCES = frozenset({"document", "tool", "model"})


def looks_like_untrusted_instruction(text: str) -> bool:
    """Return whether text tries to install a persistent instruction."""
    lowered = text.lower()
    return any(marker in lowered for marker in _INSTRUCTION_MARKERS)


def redact_assignments(text: str) -> str:
    """Redact obvious secret assignments before they are stored."""
    return _SECRET_ASSIGNMENT.sub(r"\1=[redacted]", text)
