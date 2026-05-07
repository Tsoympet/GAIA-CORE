"""GAIA core package."""
"""GAIA package."""

from .core import GaiaCore

__all__ = ["GaiaCore"]
"""GAIA core package.

GAIA is a modular, local-first autonomous intelligence operating platform.
The bootstrap package intentionally exposes platform primitives rather than a
chat-only interface.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
