from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from rich.console import Console

from semantic_query_experiment.io import read_jsonl
from semantic_query_experiment.schemas import QuerySpec
from semantic_query_experiment.statistics import (
    build_statistical_summary,
    write_statistical_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute statistical summary for the primary semantic_query contrast."
    )
    parser.add_argument("--metrics", type=Path, default=Path("reports/final/metrics.json"))
    parser.add_argument("--queries", type=Path, default=Path("data/queries/query-suite.jsonl"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/final/statistical-summary.json"),
    )
    parser.add_argument("--bootstrap-seed", type=int, default=20260507)
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    parser.add_argument(
        "--preregistration-created-commit",
        default="fbfda1673e8a72e56ced615b5427428c30ca58b1",
    )
    parser.add_argument(
        "--preregistration-last-prerun-commit",
        default="6d6e179bf9c02e35d88727a1a398c644fc6b4b47",
    )
    args = parser.parse_args()

    parsed_metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    if not isinstance(parsed_metrics, dict):
        raise SystemExit("metrics JSON must be an object")
    metrics = cast(dict[str, object], parsed_metrics)
    summary = build_statistical_summary(
        metrics=metrics,
        queries=read_jsonl(args.queries, QuerySpec),
        bootstrap_seed=args.bootstrap_seed,
        bootstrap_iterations=args.bootstrap_iterations,
        preregistration_created_commit=args.preregistration_created_commit,
        preregistration_last_prerun_commit=args.preregistration_last_prerun_commit,
    )
    write_statistical_summary(args.output, summary)

    primary = summary["primary_delta"]
    if not isinstance(primary, dict):
        raise SystemExit("statistical summary did not contain primary_delta")
    Console().print(
        "Wrote statistical summary: "
        f"{args.output} "
        f"(mean delta {primary['mean_delta']:.4f}, "
        f"decision {primary['preregistered_decision_rule_result']})"
    )
