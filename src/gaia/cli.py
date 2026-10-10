"""Command line interface for GAIA Core."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from gaia.core.runtime import RuntimeStatus, TaskRequest, create_runtime
from gaia.server.app import create_app

app = typer.Typer(help="GAIA autonomous intelligence platform CLI.")
console = Console()


@app.command()
def status(config_dir: Path = Path("config")) -> None:
    """Print the runtime bootstrap status."""
    runtime = create_runtime(config_dir=config_dir)
    console.print(runtime.status().model_dump(mode="json"))


@app.command()
def run(
    task: str,
    config_dir: Path = Path("config"),
    continuity_db: Path | None = None,
    organism_db: Path | None = None,
) -> None:
    """Run one task through the local bootstrap runtime."""
    import asyncio

    runtime = create_runtime(
        config_dir=config_dir,
        continuity_path=continuity_db,
        organism_path=organism_db,
    )
    result = asyncio.run(runtime.submit_task(TaskRequest(task=task)))
    console.print(result.model_dump(mode="json"))


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    continuity_db: Path | None = None,
    organism_db: Path | None = None,
) -> None:
    """Run the GAIA API server."""
    import uvicorn

    runtime = None
    if continuity_db is not None or organism_db is not None:
        runtime = create_runtime(
            continuity_path=continuity_db,
            organism_path=organism_db,
        )
    uvicorn.run(create_app(runtime), host=host, port=port)


@app.command()
def continuity(db: Path = Path(".gaia/continuity.sqlite3")) -> None:
    """Inspect a local continuity journal without mutating it."""
    if not db.exists():
        console.print(
            {
                "capability": "cognitive_continuity",
                "status": "unavailable",
                "durable": False,
                "reason": "Continuity journal file does not exist.",
            }
        )
        return
    from gaia.continuity.store import ContinuityStore

    store = ContinuityStore(db)
    console.print(store.status_summary())


@app.command()
def organism(db: Path = Path(".gaia/organism.sqlite3")) -> None:
    """Inspect a local Memory Organism without creating one when the file is absent."""
    if not db.exists():
        console.print(
            {
                "capability": "memory_organism",
                "status": "unavailable",
                "durable": False,
                "reason": "Memory Organism file does not exist.",
            }
        )
        return
    from gaia.organism.organism import MemoryOrganism

    console.print(MemoryOrganism(db).status())


@app.command()
def capabilities() -> None:
    """List built-in capability domains available to the orchestrator."""
    runtime = create_runtime(config_dir=Path("config"))
    for capability in runtime.capability_router.list_capabilities():
        console.print(f"[bold]{capability.name}[/bold]: {capability.description}")


def runtime_status_for_tests() -> RuntimeStatus:
    """Return a status snapshot without invoking Typer."""
    return create_runtime(config_dir=Path("config")).status()
