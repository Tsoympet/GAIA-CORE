"""Read-only catalog of GAIA tool adapters and their permission state."""

from __future__ import annotations

from dataclasses import dataclass

from gaia.security.permission_manager import Permission, PermissionManager


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Static description of a tool the runtime can name."""

    name: str
    description: str
    execution: str
    permission: Permission | None = None


@dataclass(frozen=True, slots=True)
class ToolStatus:
    """Permission-evaluated status. Status does not execute the tool."""

    name: str
    description: str
    execution: str
    permission: str | None
    available: bool
    requires_human_approval: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "execution": self.execution,
            "permission": self.permission,
            "available": self.available,
            "requires_human_approval": self.requires_human_approval,
            "reason": self.reason,
        }


_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "no_external_tool",
        "Default when a step needs no process, file, or network side effect.",
        "local",
    ),
    ToolSpec(
        "memory_manager",
        "Scoped memory write and recall for a consenting owner.",
        "local",
    ),
    ToolSpec(
        "policy_review",
        "Read-only view of permissions, audit events, and the kill switch.",
        "local",
        Permission.KERNEL_READ,
    ),
    ToolSpec(
        "voice_router",
        "Synthetic speech and typed transcripts. Real-person cloning is refused.",
        "synthetic",
    ),
    ToolSpec(
        "local_research_scratchpad",
        "Internal notes only. This tool does not fetch the network.",
        "local_notes",
    ),
    ToolSpec(
        "file_read",
        "Workspace file reads stay inside the workspace root.",
        "guarded",
        Permission.FILE_READ,
    ),
    ToolSpec(
        "file_write",
        "Workspace writes require file.write. Risky writes need human approval.",
        "approval_gated",
        Permission.FILE_WRITE,
    ),
    ToolSpec(
        "permission_checked_repo_tools",
        "Repository commands stay approval-gated and are not launched by status.",
        "approval_gated",
        Permission.SHELL_COMMAND,
    ),
    ToolSpec(
        "network",
        "Outbound network stays denied until an approved network rule exists.",
        "approval_gated",
        Permission.NETWORK_ACCESS,
    ),
)


class ToolCatalog:
    """Evaluate tool availability without executing a tool."""

    def __init__(self, specs: tuple[ToolSpec, ...] = _SPECS) -> None:
        self.specs = specs

    def describe(self, permissions: PermissionManager) -> list[ToolStatus]:
        return [self._status(spec, permissions) for spec in self.specs]

    def status(self, permissions: PermissionManager) -> dict[str, object]:
        tools = self.describe(permissions)
        return {
            "execution": "status_only",
            "count": len(tools),
            "available": sum(1 for tool in tools if tool.available),
            "approval_gated": sum(1 for tool in tools if tool.requires_human_approval),
            "tools": [tool.as_dict() for tool in tools],
        }

    def _status(self, spec: ToolSpec, permissions: PermissionManager) -> ToolStatus:
        if spec.permission is None:
            return ToolStatus(
                name=spec.name,
                description=spec.description,
                execution=spec.execution,
                permission=None,
                available=True,
                requires_human_approval=False,
                reason="no elevated permission required",
            )
        decision = permissions.check(
            spec.permission,
            "*",
            actor="tool-status",
            audit=False,
        )
        return ToolStatus(
            name=spec.name,
            description=spec.description,
            execution=spec.execution,
            permission=spec.permission.value,
            available=decision.allowed,
            requires_human_approval=decision.requires_human_approval,
            reason=decision.reason,
        )
