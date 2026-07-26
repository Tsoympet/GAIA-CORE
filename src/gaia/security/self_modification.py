"""Guardrails for controlled, human-approved self-modification."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gaia.security.permission_manager import Permission, PermissionManager

CRITICAL_PATH_PATTERNS = (
    "src/gaia/security/",
    ".github/workflows/",
    "deployment/",
    "desktop/src-tauri/",
)


@dataclass(slots=True)
class SelfModificationGuard:
    """Require approved change IDs and permissions for source modification."""

    permissions: PermissionManager
    critical_patterns: tuple[str, ...] = CRITICAL_PATH_PATTERNS
    approved_change_ids: set[str] = field(default_factory=set)

    def approve(self, change_id: str) -> None:
        if not change_id.strip():
            raise ValueError("change_id must not be empty")
        self.approved_change_ids.add(change_id)

    def validate(
        self,
        path: Path | str,
        change_id: str | None,
        actor: str = "system",
    ) -> None:
        normalized = Path(path).as_posix()
        critical = any(
            pattern in normalized
            for pattern in self.critical_patterns
        )
        if critical and not change_id:
            raise PermissionError(
                "human approval required for critical self-modification: "
                f"{normalized}"
            )
        if change_id and change_id not in self.approved_change_ids:
            raise PermissionError(
                f"unapproved self-modification change id: {change_id}"
            )
        self.permissions.require(Permission.SELF_MODIFY, normalized, actor)
