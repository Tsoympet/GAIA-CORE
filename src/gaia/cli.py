"""Command-line entry point for starting GAIA Core."""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Sequence

from .core import GaiaCore
from .core.runtime import JsonFormatter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the GAIA Core runtime.")
    parser.add_argument("--config", help="Path to a JSON or TOML config file.")
    parser.add_argument("--workspace", help="Workspace directory override.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Start the runtime, print health, and shut down immediately.",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Emit runtime logs as JSON.",
    )
    return parser


def configure_logging(*, json_logs: bool = False) -> None:
    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


async def run(args: argparse.Namespace) -> int:
    core = (
        GaiaCore.from_config_file(args.config, workspace=args.workspace)
        if args.config
        else GaiaCore(workspace=args.workspace)
    )
    await core.startup()
    print(f"GAIA Core runtime started: {core.runtime.status.value}")
    print(f"Health: {core.lifecycle.health.status.value}")
    if args.once:
        await core.shutdown()
        print("GAIA Core runtime stopped")
        return 0

    try:
        stop_event = asyncio.Event()
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await core.shutdown()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(json_logs=args.log_json)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
"""Command line interface for bootstrapping and inspecting GAIA."""

from pathlib import Path

import typer
from rich.console import Console

from gaia.core.runtime import RuntimeStatus, create_runtime
from gaia.server.app import create_app

app = typer.Typer(help="GAIA autonomous intelligence platform CLI.")
console = Console()


@app.command()
def status(config_dir: Path = Path("config")) -> None:
    """Print the runtime bootstrap status."""
    runtime = create_runtime(config_dir=config_dir)
    status_snapshot = runtime.status()
    console.print(status_snapshot.model_dump(mode="json"))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the GAIA API server."""
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)


@app.command()
def capabilities() -> None:
    """List built-in capability domains available to the orchestrator."""
    runtime = create_runtime(config_dir=Path("config"))
    for capability in runtime.capability_router.list_capabilities():
        console.print(f"[bold]{capability.name}[/bold]: {capability.description}")


def runtime_status_for_tests() -> RuntimeStatus:
    """Return a status snapshot without invoking Typer."""
    return create_runtime(config_dir=Path("config")).status()
