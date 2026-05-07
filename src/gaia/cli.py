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
