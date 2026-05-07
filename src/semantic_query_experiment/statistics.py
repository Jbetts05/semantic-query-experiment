from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import cast

from semantic_query_experiment.schemas import QuerySpec

CONTROL_ARM = "hybrid_semantic_query_control"
DETERMINISTIC_ARM = "hybrid_semantic_query_deterministic"
PRIMARY_METRIC = "ndcg_at_10"


def build_statistical_summary(
    *,
    metrics: dict[str, object],
    queries: list[QuerySpec],
    bootstrap_seed: int,
    bootstrap_iterations: int,
    preregistration_created_commit: str,
    preregistration_last_prerun_commit: str,
) -> dict[str, object]:
    """Build the statistical summary used by the whitepaper and evidence bundle."""
    deltas_by_query = primary_deltas_by_query(metrics)
    deltas = [deltas_by_query[query_id] for query_id in sorted(deltas_by_query)]
    category_by_query = {query.query_id: query.category for query in queries}
    category_counts = Counter(query.category for query in queries)
    category_deltas: dict[str, list[float]] = defaultdict(list)
    for query_id, delta in deltas_by_query.items():
        category_deltas[category_by_query[query_id]].append(delta)
    mean_delta = mean(deltas)
    bootstrap = paired_bootstrap_ci(
        deltas,
        seed=bootstrap_seed,
        iterations=bootstrap_iterations,
    )

    return {
        "schema_version": 1,
        "source_metrics": "reports/final/metrics.json",
        "source_queries": "data/queries/query-suite.jsonl",
        "notes": [
            "Category-level deltas are exploratory point estimates and are not "
            "multiple-comparison corrected.",
            "Primary bootstrap confidence interval was computed from per-query deltas "
            "in reports/final/metrics.json.",
            "Wilcoxon signed-rank uses a normal approximation with continuity correction "
            "and excludes zero deltas.",
        ],
        "query_category_counts": dict(sorted(category_counts.items())),
        "primary_delta": {
            "contrast": ("hybrid_semantic_query_deterministic minus hybrid_semantic_query_control"),
            "metric": PRIMARY_METRIC,
            "query_count": len(deltas),
            "mean_delta": mean_delta,
            "bootstrap": bootstrap,
            "wilcoxon_signed_rank": wilcoxon_signed_rank(deltas),
            "positive_delta_share": share(deltas, lambda value: value > 0),
            "negative_delta_share": share(deltas, lambda value: value < 0),
            "zero_delta_share": share(deltas, lambda value: value == 0),
            "primary_decision_rule": (
                "Support requires mean paired delta NDCG@10 >= +0.02 and a paired "
                "bootstrap 95% confidence interval entirely above 0.00."
            ),
            "preregistered_decision_rule_result": decision_rule_result(
                mean_delta=mean_delta,
                bootstrap_lower=_as_float(bootstrap["lower"]),
            ),
        },
        "category_delta_summary": [
            {
                "category": category,
                "query_count": len(values),
                "mean_delta_ndcg_at_10": mean(values),
                "positive_delta_share": share(values, lambda value: value > 0),
                "negative_delta_share": share(values, lambda value: value < 0),
                "zero_delta_share": share(values, lambda value: value == 0),
                "multiple_comparison_corrected": False,
            }
            for category, values in sorted(category_deltas.items())
        ],
        "aggregate_by_arm": aggregate_by_arm(metrics),
        "preregistration": {
            "path": "docs/preregistration.md",
            "created_commit": preregistration_created_commit,
            "last_prerun_commit_touching_file": preregistration_last_prerun_commit,
        },
    }


def write_statistical_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def decision_rule_result(*, mean_delta: float, bootstrap_lower: float) -> str:
    if mean_delta >= 0.02 and bootstrap_lower > 0:
        return "supported"
    return "not_supported"


def primary_deltas_by_query(metrics: dict[str, object]) -> dict[str, float]:
    """Return deterministic-control NDCG@10 deltas keyed by query id."""
    rows = _as_rows(metrics.get("per_query"))
    by_query: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        arm = _as_str(row.get("arm"))
        query_id = _as_str(row.get("query_id"))
        if not arm or not query_id or arm not in {CONTROL_ARM, DETERMINISTIC_ARM}:
            continue
        by_query[query_id][arm] = _as_float(row.get(PRIMARY_METRIC))
    return {
        query_id: arms[DETERMINISTIC_ARM] - arms[CONTROL_ARM]
        for query_id, arms in by_query.items()
        if CONTROL_ARM in arms and DETERMINISTIC_ARM in arms
    }


def paired_bootstrap_ci(
    values: list[float],
    *,
    seed: int,
    iterations: int,
    confidence_level: float = 0.95,
) -> dict[str, object]:
    """Compute a paired nonparametric bootstrap CI over query-level deltas."""
    if not values:
        raise ValueError("values must not be empty")
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rng = random.Random(seed)
    sample_size = len(values)
    bootstrap_means = [
        mean([values[rng.randrange(sample_size)] for _ in range(sample_size)])
        for _ in range(iterations)
    ]
    bootstrap_means.sort()
    alpha = 1 - confidence_level
    lower_index = int((alpha / 2) * iterations)
    upper_index = int((1 - alpha / 2) * iterations) - 1
    return {
        "seed": seed,
        "iterations": iterations,
        "confidence_level": confidence_level,
        "lower": bootstrap_means[lower_index],
        "upper": bootstrap_means[upper_index],
        "method": "paired nonparametric bootstrap over query-level deltas",
    }


def wilcoxon_signed_rank(values: list[float]) -> dict[str, object]:
    """Compute a two-sided Wilcoxon signed-rank normal approximation."""
    nonzero = [value for value in values if value != 0]
    if not nonzero:
        return {
            "method": (
                "normal approximation with continuity correction; zero deltas excluded; "
                "statistic = min(W+, W-)"
            ),
            "nonzero_count": 0,
            "positive_rank_sum": 0.0,
            "negative_rank_sum": 0.0,
            "statistic": 0.0,
            "z": 0.0,
            "p_value_two_sided": 1.0,
        }

    ranked = _average_abs_ranks(nonzero)
    positive_rank_sum = sum(rank for value, rank in ranked if value > 0)
    negative_rank_sum = sum(rank for value, rank in ranked if value < 0)
    statistic = min(positive_rank_sum, negative_rank_sum)
    n = len(nonzero)
    expected = n * (n + 1) / 4
    variance = n * (n + 1) * (2 * n + 1) / 24
    correction = 0.5 if statistic < expected else -0.5
    z = (statistic - expected + correction) / math.sqrt(variance)
    p_value = math.erfc(abs(z) / math.sqrt(2))
    return {
        "method": (
            "normal approximation with continuity correction; zero deltas excluded; "
            "statistic = min(W+, W-)"
        ),
        "nonzero_count": n,
        "positive_rank_sum": positive_rank_sum,
        "negative_rank_sum": negative_rank_sum,
        "statistic": statistic,
        "z": z,
        "p_value_two_sided": p_value,
    }


def aggregate_by_arm(metrics: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = _as_rows(metrics.get("aggregate"))
    return {str(row["arm"]): row for row in rows if "arm" in row}


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def share(values: list[float], predicate: Callable[[float], bool]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if predicate(value)) / len(values)


def _average_abs_ranks(values: list[float]) -> list[tuple[float, float]]:
    ordered = sorted(enumerate(values), key=lambda item: (abs(item[1]), item[0]))
    ranks_by_index: dict[int, float] = {}
    rank = 1
    cursor = 0
    while cursor < len(ordered):
        group_end = cursor + 1
        abs_value = abs(ordered[cursor][1])
        while group_end < len(ordered) and abs(ordered[group_end][1]) == abs_value:
            group_end += 1
        group_size = group_end - cursor
        average_rank = (rank + rank + group_size - 1) / 2
        for index, _value in ordered[cursor:group_end]:
            ranks_by_index[index] = average_rank
        rank += group_size
        cursor = group_end
    return [(value, ranks_by_index[index]) for index, value in enumerate(values)]


def _as_rows(value: object) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], value) if isinstance(value, list) else []


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_float(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
