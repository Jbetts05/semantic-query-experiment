import argparse

from rich.console import Console

from semantic_query_experiment.config import load_experiment_config
from semantic_query_experiment.data_generation.generator import (
    GenerationPaths,
    generate_dataset,
    write_generated_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic GxP data.")
    parser.add_argument("--chunk-count", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    config = load_experiment_config()
    seed = args.seed if args.seed is not None else config.random_seed
    chunk_count = (
        args.chunk_count if args.chunk_count is not None else config.target_indexed_chunks_min
    )

    dataset = generate_dataset(requested_chunk_count=chunk_count, seed=seed)
    paths = GenerationPaths()
    write_generated_dataset(dataset, paths)

    console = Console()
    console.print(
        f"Generated {dataset.manifest.actual_chunk_count} chunks, "
        f"{dataset.manifest.query_count} queries, and "
        f"{dataset.manifest.hard_negative_count} hard negatives."
    )
    console.print(f"Wrote manifest: {paths.manifest_path}")
