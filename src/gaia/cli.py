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
