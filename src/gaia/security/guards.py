"""Command, file, and network guards for controlled tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shlex
from urllib.parse import urlparse

from .permission_manager import Permission, PermissionManager

DANGEROUS_COMMAND_PREFIXES = {"rm", "mkfs", "shutdown", "reboot", "dd", "chmod", "chown"}


@dataclass(slots=True)
class CommandGuard:
    permissions: PermissionManager
    blocked_prefixes: set[str] = field(default_factory=lambda: set(DANGEROUS_COMMAND_PREFIXES))

    def validate(self, command: str, actor: str = "system") -> str:
        parts = shlex.split(command)
        if not parts:
            raise PermissionError("empty command is not executable")
        executable = Path(parts[0]).name
        if executable in self.blocked_prefixes:
            raise PermissionError(f"blocked command prefix: {executable}")
        self.permissions.require(Permission.COMMAND_EXECUTE, executable, actor)
        return command


@dataclass(slots=True)
class FileGuard:
    permissions: PermissionManager
    root: Path = field(default_factory=lambda: Path.cwd())

    def resolve(self, path: Path | str) -> Path:
        resolved = (self.root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        if self.root.resolve() not in (resolved, *resolved.parents):
            raise PermissionError(f"path escapes workspace root: {resolved}")
        return resolved

    def require_read(self, path: Path | str, actor: str = "system") -> Path:
        resolved = self.resolve(path)
        self.permissions.require(Permission.FILE_READ, str(resolved), actor)
        return resolved

    def require_write(self, path: Path | str, actor: str = "system") -> Path:
        resolved = self.resolve(path)
        self.permissions.require(Permission.FILE_WRITE, str(resolved), actor)
        return resolved


@dataclass(slots=True)
class NetworkGuard:
    permissions: PermissionManager
    blocked_hosts: set[str] = field(default_factory=set)

    def validate_url(self, url: str, actor: str = "system") -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise PermissionError(f"unsupported network URL: {url}")
        if parsed.hostname in self.blocked_hosts:
            raise PermissionError(f"blocked network host: {parsed.hostname}")
        self.permissions.require(Permission.NETWORK_CONNECT, parsed.hostname or parsed.netloc, actor)
        return url
