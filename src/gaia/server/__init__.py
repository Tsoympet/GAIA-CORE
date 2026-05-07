"""GAIA server package."""

from .app import app, create_app

__all__ = ["app", "create_app"]
"""FastAPI server interfaces for GAIA runtime access."""

from gaia.server.app import create_app

__all__ = ["create_app"]
