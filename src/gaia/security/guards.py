"""Command, file, and network guards for controlled tool execution."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from gaia.security.permission_manager import Permission, PermissionManager

DANGEROUS_COMMAND_PREFIXES = {
    "rm",
    "mkfs",
    "shutdown",
    "reboot",
    "dd",
    "chmod",
    "chown",
}


@dataclass(slots=True)
class CommandGuard:
    """Validate shell commands against deny rules and explicit permissions."""

    permissions: PermissionManager
    blocked_prefixes: set[str] = field(
        default_factory=lambda: set(DANGEROUS_COMMAND_PREFIXES)
    )

    def validate(self, command: str, actor: str = "system") -> str:
        parts = shlex.split(command)
        if not parts:
            raise PermissionError("empty command is not executable")
        executable = Path(parts[0]).name
        if executable in self.blocked_prefixes:
            raise PermissionError(f"blocked command prefix: {executable}")
        self.permissions.require(Permission.SHELL_COMMAND, command, actor)
        return command


@dataclass(slots=True)
class FileGuard:
    """Confine file access to a workspace root and enforce permissions."""

    permissions: PermissionManager
    root: Path = field(default_factory=Path.cwd)

    def resolve(self, path: Path | str) -> Path:
        candidate = Path(path)
        resolved = (
            (self.root / candidate).resolve()
            if not candidate.is_absolute()
            else candidate.resolve()
        )
        root = self.root.resolve()
        if root not in (resolved, *resolved.parents):
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
    """Validate HTTP(S) destinations and enforce network permission."""

    permissions: PermissionManager
    blocked_hosts: set[str] = field(default_factory=set)

    def validate_url(self, url: str, actor: str = "system") -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise PermissionError(f"unsupported network URL: {url}")
        if parsed.hostname in self.blocked_hosts:
            raise PermissionError(f"blocked network host: {parsed.hostname}")
        self.permissions.require(
            Permission.NETWORK_ACCESS,
            parsed.hostname or parsed.netloc,
            actor,
        )
        return url
