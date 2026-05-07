"""Run GAIA Core with ``python -m gaia``."""

from .cli import main

raise SystemExit(main())
"""Module entry point for ``python -m gaia``."""

from gaia.cli import app

if __name__ == "__main__":
    app()
