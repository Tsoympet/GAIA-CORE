"""agents typed route module."""

from __future__ import annotations

from .common import status_router

router = status_router("/agents", "agents", "agents")
