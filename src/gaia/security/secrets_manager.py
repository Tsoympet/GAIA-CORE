"""Local secrets registry with redaction-first access semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
import os

from .permission_manager import Permission, PermissionManager


@dataclass(slots=True)
class SecretRecord:
    name: str
    value: str
    source: str = "memory"

    @property
    def redacted(self) -> str:
        if len(self.value) <= 4:
            return "****"
        return f"{self.value[:2]}{'*' * max(4, len(self.value) - 4)}{self.value[-2:]}"


@dataclass(slots=True)
class SecretsManager:
    permissions: PermissionManager
    _secrets: dict[str, SecretRecord] = field(default_factory=dict)

    def set(self, name: str, value: str, source: str = "memory") -> None:
        self._secrets[name] = SecretRecord(name=name, value=value, source=source)

    def load_env(self, names: list[str]) -> None:
        for name in names:
            if name in os.environ:
                self.set(name, os.environ[name], source="environment")

    def get(self, name: str, actor: str = "system") -> str:
        self.permissions.require(Permission.SECRET_READ, name, actor)
        return self._secrets[name].value

    def list_redacted(self) -> list[dict[str, str]]:
        return [{"name": s.name, "value": s.redacted, "source": s.source} for s in self._secrets.values()]
