"""Compatibility exports for capability routing imports."""

from gaia.capabilities.capability_registry import Capability, CapabilityRegistry
from gaia.capabilities.capability_router import (
    CapabilityRouter,
    RouteDecision,
    create_default_capability_router,
)

__all__ = [
    "Capability",
    "CapabilityRegistry",
    "CapabilityRouter",
    "RouteDecision",
    "create_default_capability_router",
]
