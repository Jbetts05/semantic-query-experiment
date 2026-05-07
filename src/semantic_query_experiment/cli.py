from typing import Annotated

import typer
from rich.console import Console

from semantic_query_experiment import __version__

app = typer.Typer(
    name="semqry",
    help="Utilities for the Azure AI Search semantic_query experiment.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the package version and exit."),
    ] = False,
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()


@app.command()
def status() -> None:
    """Show the current implementation status."""
    console.print("Repository foundation is ready. Azure provisioning is not wired yet.")
