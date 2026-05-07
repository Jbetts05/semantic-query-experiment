from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import cast

from semantic_query_experiment.schemas import ArtifactRecord, QuerySpec, RelevanceLabel, SearchArm


def evaluate_results(
    *,
    queries: list[QuerySpec],
    labels: list[RelevanceLabel],
    records: list[ArtifactRecord],
) -> dict[str, object]:
    """Evaluate ranked search results with graded relevance metrics."""
    labels_by_query: dict[str, dict[str, int]] = defaultdict(dict)
    for label in labels:
        labels_by_query[label.query_id][label.document_id] = label.relevance

    category_by_query = {query.query_id: query.category for query in queries}
    records_by_arm_query: dict[str, dict[str, list[ArtifactRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        records_by_arm_query[str(record.arm)][record.query_id].append(record)

    per_query: list[dict[str, object]] = []
    for arm, by_query in sorted(records_by_arm_query.items()):
        for query_id, ranked_records in sorted(by_query.items()):
            ranked = sorted(ranked_records, key=lambda record: record.rank)
            ranked_ids = [record.document_id for record in ranked]
            label_map = labels_by_query[query_id]
            per_query.append(
                {
                    "arm": arm,
                    "query_id": query_id,
                    "category": category_by_query[query_id],
                    "ndcg_at_3": ndcg_at_k(ranked_ids, label_map, 3),
                    "ndcg_at_10": ndcg_at_k(ranked_ids, label_map, 10),
                    "mrr_at_10": mrr_at_k(ranked_ids, label_map, 10),
                    "recall_at_50": recall_at_k(ranked_ids, label_map, 50),
                    "hit_at_1": hit_at_k(ranked_ids, label_map, 1),
                    "hit_at_3": hit_at_k(ranked_ids, label_map, 3),
                    "hit_at_5": hit_at_k(ranked_ids, label_map, 5),
                    "hit_at_10": hit_at_k(ranked_ids, label_map, 10),
                    "latency_ms": _first_latency_ms(ranked),
                }
            )

    aggregate = _aggregate(per_query, group_keys=("arm",))
    by_category = _aggregate(per_query, group_keys=("arm", "category"))
    primary_delta = _primary_delta(per_query)
    executed_query_count = len({str(row["query_id"]) for row in per_query})
    return {
        "schema_version": 1,
        "query_count": executed_query_count,
        "available_query_count": len(queries),
        "result_count": len(records),
        "aggregate": aggregate,
        "by_category": by_category,
        "primary_delta": primary_delta,
        "per_query": per_query,
    }


def write_report_bundle(metrics: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(render_markdown_report(metrics), encoding="utf-8")
    (output_dir / "ndcg-at-10.svg").write_text(render_ndcg_svg(metrics), encoding="utf-8")


def render_markdown_report(metrics: dict[str, object]) -> str:
    aggregate = _as_rows(metrics["aggregate"])
    primary_delta = _as_mapping(metrics["primary_delta"])
    lines = [
        "# Semantic query experiment report",
        "",
        f"Queries: `{metrics['query_count']}`  ",
        f"Ranked result records: `{metrics['result_count']}`",
        "",
        "## Primary contrast",
        "",
        (
            "Hybrid semantic query deterministic minus identical-control "
            f"NDCG@10 delta: `{primary_delta.get('mean_delta_ndcg_at_10', 0):.4f}`"
        ),
        "",
        "## Aggregate metrics by arm",
        "",
        "| Arm | NDCG@10 | NDCG@3 | MRR@10 | Recall@50 | Hit@1 | Latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in aggregate:
        lines.append(
            f"| `{row['arm']}` | {row['ndcg_at_10']:.4f} | {row['ndcg_at_3']:.4f} | "
            f"{row['mrr_at_10']:.4f} | {row['recall_at_50']:.4f} | "
            f"{row['hit_at_1']:.4f} | {row['latency_ms']:.1f} |"
        )
    lines.extend(
        [
            "",
            "![NDCG@10 by arm](ndcg-at-10.svg)",
            "",
            "## Notes",
            "",
            "- Results are from a synthetic GxP corpus with generator-asserted labels.",
            "- The primary comparison is paired by query.",
            "- The LLM rewrite arm is intentionally excluded until rewrite prompts are frozen.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_ndcg_svg(metrics: dict[str, object]) -> str:
    rows = _as_rows(metrics["aggregate"])
    width = 980
    height = 360
    chart_left = 260
    chart_width = 640
    bar_height = 28
    gap = 18
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        'viewBox="0 0 980 360" role="img" aria-label="NDCG at 10 by arm">',
        '<rect width="980" height="360" fill="#0b1020"/>',
        '<text x="32" y="42" fill="#f8fafc" font-family="Segoe UI, Arial" '
        'font-size="24" font-weight="700">NDCG@10 by experiment arm</text>',
    ]
    for index, row in enumerate(rows):
        y = 78 + index * (bar_height + gap)
        score = _float_value(row["ndcg_at_10"])
        bar_width = int(chart_width * score)
        svg_parts.extend(
            [
                f'<text x="32" y="{y + 20}" fill="#cbd5e1" font-family="Segoe UI, Arial" '
                f'font-size="13">{row["arm"]}</text>',
                f'<rect x="{chart_left}" y="{y}" width="{chart_width}" height="{bar_height}" '
                'rx="8" fill="#1e293b"/>',
                f'<rect x="{chart_left}" y="{y}" width="{bar_width}" height="{bar_height}" '
                'rx="8" fill="#38bdf8"/>',
                f'<text x="{chart_left + chart_width + 16}" y="{y + 20}" fill="#f8fafc" '
                f'font-family="Segoe UI, Arial" font-size="14">{score:.3f}</text>',
            ]
        )
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def ndcg_at_k(
    ranked_document_ids: list[str],
    relevance_by_document: dict[str, int],
    k: int,
) -> float:
    dcg = 0.0
    for index, document_id in enumerate(ranked_document_ids[:k], start=1):
        relevance = relevance_by_document.get(document_id, 0)
        dcg += (2**relevance - 1) / math.log2(index + 1)
    ideal = sorted(relevance_by_document.values(), reverse=True)[:k]
    ideal_dcg = sum(
        (2**relevance - 1) / math.log2(index + 1) for index, relevance in enumerate(ideal, start=1)
    )
    return dcg / ideal_dcg if ideal_dcg else 0.0


def mrr_at_k(
    ranked_document_ids: list[str],
    relevance_by_document: dict[str, int],
    k: int,
) -> float:
    for index, document_id in enumerate(ranked_document_ids[:k], start=1):
        if relevance_by_document.get(document_id, 0) == 3:
            return 1 / index
    return 0.0


def recall_at_k(
    ranked_document_ids: list[str],
    relevance_by_document: dict[str, int],
    k: int,
) -> float:
    relevant = {
        document_id for document_id, relevance in relevance_by_document.items() if relevance > 0
    }
    if not relevant:
        return 0.0
    found = set(ranked_document_ids[:k]) & relevant
    return len(found) / len(relevant)


def hit_at_k(
    ranked_document_ids: list[str],
    relevance_by_document: dict[str, int],
    k: int,
) -> float:
    gold = {
        document_id for document_id, relevance in relevance_by_document.items() if relevance == 3
    }
    return float(bool(set(ranked_document_ids[:k]) & gold))


def _aggregate(
    per_query: list[dict[str, object]],
    *,
    group_keys: tuple[str, ...],
) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in per_query:
        groups[tuple(str(row[key]) for key in group_keys)].append(row)
    output: list[dict[str, object]] = []
    metrics = (
        "ndcg_at_3",
        "ndcg_at_10",
        "mrr_at_10",
        "recall_at_50",
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "hit_at_10",
        "latency_ms",
    )
    for key_values, rows in sorted(groups.items()):
        aggregate_row: dict[str, object] = dict(zip(group_keys, key_values, strict=True))
        for metric in metrics:
            values = [_float_value(row[metric]) for row in rows]
            aggregate_row[metric] = sum(values) / len(values)
        aggregate_row["query_count"] = len(rows)
        output.append(aggregate_row)
    return output


def _primary_delta(per_query: list[dict[str, object]]) -> dict[str, object]:
    control = {
        str(row["query_id"]): _float_value(row["ndcg_at_10"])
        for row in per_query
        if row["arm"] == SearchArm.HYBRID_SEMANTIC_QUERY_CONTROL
    }
    deterministic = {
        str(row["query_id"]): _float_value(row["ndcg_at_10"])
        for row in per_query
        if row["arm"] == SearchArm.HYBRID_SEMANTIC_QUERY_DETERMINISTIC
    }
    common = sorted(set(control) & set(deterministic))
    deltas = [deterministic[query_id] - control[query_id] for query_id in common]
    return {
        "query_count": len(common),
        "mean_delta_ndcg_at_10": sum(deltas) / len(deltas) if deltas else 0.0,
    }


def _first_latency_ms(records: list[ArtifactRecord]) -> int:
    if not records:
        return 0
    value = records[0].metadata.get("elapsed_ms")
    return value if isinstance(value, int) else 0


def _as_rows(value: object) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], value) if isinstance(value, list) else []


def _as_mapping(value: object) -> dict[str, float]:
    return cast(dict[str, float], value) if isinstance(value, dict) else {}


def _float_value(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
