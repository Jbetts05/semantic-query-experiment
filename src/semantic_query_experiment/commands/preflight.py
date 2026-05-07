from rich.console import Console

from semantic_query_experiment.azure.preflight import (
    PreflightPaths,
    run_preflight,
    write_preflight_result,
)


def main() -> None:
    console = Console()
    paths = PreflightPaths()
    result = run_preflight(paths=paths)
    write_preflight_result(result, paths.output_path)

    if result.selected_region:
        console.print(f"Selected candidate region: {result.selected_region}")
    else:
        console.print("No candidate region passed all required preflight checks.")
    console.print(f"Wrote {paths.output_path}")
