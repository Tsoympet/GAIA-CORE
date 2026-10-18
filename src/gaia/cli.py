"""Command line interface for GAIA Core."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from gaia.core.runtime import DEFAULT_KERNEL_DB_PATH, RuntimeStatus, TaskRequest, create_runtime
from gaia.security.field_cipher import (
    DataKeyError,
    FieldCipher,
    read_data_key,
    write_data_key,
)
from gaia.server.app import create_app

app = typer.Typer(help="GAIA autonomous intelligence platform CLI.")
console = Console()


@app.command()
def status(config_dir: Path = Path("config")) -> None:
    """Print the runtime bootstrap status."""
    runtime = create_runtime(
        config_dir=config_dir,
        kernel_db_path=DEFAULT_KERNEL_DB_PATH,
    )
    console.print(runtime.status().model_dump(mode="json"))


@app.command()
def run(
    task: str,
    config_dir: Path = Path("config"),
    continuity_db: Path | None = None,
    organism_db: Path | None = None,
    data_key_file: Path | None = None,
    repository_root: Path | None = None,
) -> None:
    """Run one task through the local bootstrap runtime."""
    import asyncio

    runtime = create_runtime(
        config_dir=config_dir,
        kernel_db_path=DEFAULT_KERNEL_DB_PATH,
        continuity_path=continuity_db,
        organism_path=organism_db,
        data_key=_load_data_key(data_key_file),
        repository_root=repository_root,
    )
    result = asyncio.run(runtime.submit_task(TaskRequest(task=task)))
    console.print(result.model_dump(mode="json"))


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    continuity_db: Path | None = None,
    organism_db: Path | None = None,
    data_key_file: Path | None = None,
    repository_root: Path | None = None,
) -> None:
    """Run the GAIA API server with durable Cognitive Kernel persistence."""
    import uvicorn

    runtime = create_runtime(
        config_dir=Path("config"),
        kernel_db_path=DEFAULT_KERNEL_DB_PATH,
        continuity_path=continuity_db,
        organism_path=organism_db,
        data_key=_load_data_key(data_key_file),
        repository_root=repository_root,
    )
    uvicorn.run(create_app(runtime), host=host, port=port)


@app.command()
def continuity(
    db: Path = Path(".gaia/continuity.sqlite3"),
    data_key_file: Path | None = None,
) -> None:
    """Inspect a local continuity journal without running recovery.

    A data key seals any plaintext fields already in the file.
    """
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

    try:
        store = ContinuityStore(db, cipher=_cipher(data_key_file))
        console.print(store.status_summary())
    except DataKeyError as exc:
        console.print(
            {
                "capability": "cognitive_continuity",
                "status": "degraded",
                "reason": str(exc),
            }
        )


@app.command()
def organism(
    db: Path = Path(".gaia/organism.sqlite3"),
    data_key_file: Path | None = None,
) -> None:
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

    try:
        console.print(MemoryOrganism(db, cipher=_cipher(data_key_file)).status())
    except DataKeyError as exc:
        console.print(
            {
                "capability": "memory_organism",
                "status": "degraded",
                "reason": str(exc),
            }
        )


@app.command("data-key")
def data_key(path: Path = Path(".gaia/data.key")) -> None:
    """Create a local 32-byte data key. An existing file is not overwritten."""
    try:
        write_data_key(path)
    except DataKeyError as exc:
        console.print({"status": "refused", "reason": str(exc)})
        raise typer.Exit(code=1) from exc
    console.print({"status": "created", "path": str(path), "bytes": 32})


def _load_data_key(path: Path | None) -> bytes | None:
    if path is None:
        return None
    return read_data_key(path)


def _cipher(path: Path | None) -> FieldCipher | None:
    key = _load_data_key(path)
    if key is None:
        return None
    return FieldCipher(key)


@app.command()
def capabilities() -> None:
    """List built-in capability domains available to the orchestrator."""
    runtime = create_runtime(
        config_dir=Path("config"),
        kernel_db_path=DEFAULT_KERNEL_DB_PATH,
    )
    for capability in runtime.capability_router.list_capabilities():
        console.print(f"[bold]{capability.name}[/bold]: {capability.description}")


def runtime_status_for_tests() -> RuntimeStatus:
    """Return a status snapshot without invoking Typer."""
    return create_runtime(config_dir=Path("config")).status()
