from rich.console import Console

console = Console()


def run_placeholder(command_name: str, next_phase: str) -> None:
    """Print a safe placeholder message for a future implementation phase."""
    console.print(f"{command_name}: placeholder ready.")
    console.print(f"Next implementation phase: {next_phase}.")
