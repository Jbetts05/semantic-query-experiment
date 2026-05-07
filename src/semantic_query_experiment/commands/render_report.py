from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from semantic_query_experiment.evaluation import evaluate_results, write_report_bundle
from semantic_query_experiment.io import read_jsonl
from semantic_query_experiment.schemas import ArtifactRecord, QuerySpec, RelevanceLabel


def main() -> None:
    parser = argparse.ArgumentParser(description="Render metrics, charts, and report.")
    parser.add_argument("--queries", type=Path, default=Path("data/queries/query-suite.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path("data/labels/relevance-labels.jsonl"))
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("reports/runs/full-suite/results.jsonl"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports/final"))
    args = parser.parse_args()

    metrics = evaluate_results(
        queries=read_jsonl(args.queries, QuerySpec),
        labels=read_jsonl(args.labels, RelevanceLabel),
        records=read_jsonl(args.results, ArtifactRecord),
    )
    write_report_bundle(metrics, args.output_dir)

    console = Console()
    console.print(f"Wrote report bundle: {args.output_dir}")
