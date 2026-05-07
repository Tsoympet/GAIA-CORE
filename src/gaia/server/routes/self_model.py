"""self_model typed route module."""

from __future__ import annotations

from .common import status_router

router = status_router("/self-model", "self-model", "self-model")
