"""GAIA simulated self-model package."""

from gaia.self_model.capability_self_map import CapabilityEntry, CapabilitySelfMap
from gaia.self_model.limitation_registry import Limitation, LimitationRegistry
from gaia.self_model.self_model import (
    SelfModelSnapshot,
    SimulatedSelfModel,
    build_runtime_self_model,
)

__all__ = [
    "CapabilityEntry",
    "CapabilitySelfMap",
    "Limitation",
    "LimitationRegistry",
    "SelfModelSnapshot",
    "SimulatedSelfModel",
    "build_runtime_self_model",
]
