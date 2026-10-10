"""Validated Cognitive Kernel configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from gaia.kernel.resource_budget import ResourceBudget


class KernelPersistenceConfig(BaseModel):
    """Persistence settings for the kernel store."""

    db_path: str = ".gaia/kernel.sqlite3"
    schema_version: int = 1


class KernelEventsConfig(BaseModel):
    """Event log settings."""

    memory_limit: int = 256
    default_list_limit: int = 100


class KernelSecurityConfig(BaseModel):
    """Permission names used by kernel operator APIs."""

    read_permission: str = "kernel.read"
    admin_permission: str = "kernel.admin"
    delete_permission: str = "kernel.delete"
    backup_permission: str = "kernel.backup"
    risky_admin_requires_human_approval: bool = True


class KernelConfig(BaseModel):
    """Top-level validated kernel configuration."""

    enabled: bool = True
    local_first: bool = True
    persistence: KernelPersistenceConfig = Field(default_factory=KernelPersistenceConfig)
    budgets: ResourceBudget = Field(default_factory=ResourceBudget)
    events: KernelEventsConfig = Field(default_factory=KernelEventsConfig)
    security: KernelSecurityConfig = Field(default_factory=KernelSecurityConfig)


def load_kernel_config(config_dir: Path | str = Path("config")) -> KernelConfig:
    """Load ``kernel.yaml`` when present, otherwise return defaults."""
    path = Path(config_dir) / "kernel.yaml"
    if not path.exists():
        return KernelConfig()
    loaded: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("kernel.yaml root must be a mapping")
    root = loaded.get("kernel", loaded)
    if not isinstance(root, dict):
        raise ValueError("kernel.yaml 'kernel' key must be a mapping")
    return KernelConfig.model_validate(root)
