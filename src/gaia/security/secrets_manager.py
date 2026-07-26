"""Local secrets registry with redaction-first access semantics."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from gaia.security.permission_manager import Permission, PermissionManager


@dataclass(slots=True)
class SecretRecord:
    name: str
    value: str
    source: str = "memory"

    @property
    def redacted(self) -> str:
        if len(self.value) <= 4:
            return "****"
        hidden_length = max(4, len(self.value) - 4)
        return (
            f"{self.value[:2]}"
            f"{'*' * hidden_length}"
            f"{self.value[-2:]}"
        )


@dataclass(slots=True)
class SecretsManager:
    """Store secrets locally and require approval-gated reads."""

    permissions: PermissionManager
    _secrets: dict[str, SecretRecord] = field(default_factory=dict)

    def set(
        self,
        name: str,
        value: str,
        source: str = "memory",
    ) -> None:
        if not name.strip():
            raise ValueError("secret name must not be empty")
        self._secrets[name] = SecretRecord(
            name=name,
            value=value,
            source=source,
        )

    def load_env(self, names: list[str]) -> None:
        for name in names:
            if name in os.environ:
                self.set(name, os.environ[name], source="environment")

    def get(self, name: str, actor: str = "system") -> str:
        self.permissions.require(Permission.SECRET_READ, name, actor)
        return self._secrets[name].value

    def list_redacted(self) -> list[dict[str, str]]:
        return [
            {
                "name": secret.name,
                "value": secret.redacted,
                "source": secret.source,
            }
            for secret in self._secrets.values()
        ]
