from semantic_query_experiment.schemas import QuerySpec
from semantic_query_experiment.statistics import (
    build_statistical_summary,
    decision_rule_result,
    primary_deltas_by_query,
    wilcoxon_signed_rank,
)


def test_primary_deltas_by_query() -> None:
    metrics: dict[str, object] = {
        "aggregate": [],
        "per_query": [
            {
                "arm": "hybrid_semantic_query_control",
                "query_id": "q-1",
                "ndcg_at_10": 0.2,
            },
            {
                "arm": "hybrid_semantic_query_deterministic",
                "query_id": "q-1",
                "ndcg_at_10": 0.5,
            },
        ],
    }

    assert primary_deltas_by_query(metrics) == {"q-1": 0.3}


def test_build_statistical_summary_includes_decision_and_wilcoxon() -> None:
    metrics: dict[str, object] = {
        "aggregate": [{"arm": "hybrid_semantic_query_control", "ndcg_at_10": 0.3}],
        "per_query": [
            {
                "arm": "hybrid_semantic_query_control",
                "query_id": "q-1",
                "ndcg_at_10": 0.5,
            },
            {
                "arm": "hybrid_semantic_query_deterministic",
                "query_id": "q-1",
                "ndcg_at_10": 0.4,
            },
            {
                "arm": "hybrid_semantic_query_control",
                "query_id": "q-2",
                "ndcg_at_10": 0.5,
            },
            {
                "arm": "hybrid_semantic_query_deterministic",
                "query_id": "q-2",
                "ndcg_at_10": 0.7,
            },
        ],
    }
    queries = [
        QuerySpec(
            query_id="q-1",
            category="id_lookup",
            search_text="DEV-1",
            semantic_intent="What resolved DEV-1?",
            expected_document_ids=["doc-1"],
        ),
        QuerySpec(
            query_id="q-2",
            category="fielded_filter",
            search_text="product:x",
            semantic_intent="What resolved product x?",
            expected_document_ids=["doc-2"],
        ),
    ]

    summary = build_statistical_summary(
        metrics=metrics,
        queries=queries,
        bootstrap_seed=7,
        bootstrap_iterations=10,
        preregistration_created_commit="created",
        preregistration_last_prerun_commit="frozen",
    )

    assert summary["query_category_counts"] == {"fielded_filter": 1, "id_lookup": 1}
    primary = summary["primary_delta"]
    assert isinstance(primary, dict)
    assert primary["preregistered_decision_rule_result"] == "not_supported"
    assert "wilcoxon_signed_rank" in primary
    assert "primary_decision_rule" in primary


def test_wilcoxon_signed_rank_excludes_zero_deltas() -> None:
    result = wilcoxon_signed_rank([0.0, -0.2, 0.1])

    assert result["nonzero_count"] == 2
    assert result["statistic"] == 1.0
    assert "statistic = min(W+, W-)" in str(result["method"])


def test_decision_rule_result_is_derived_from_effect_and_ci() -> None:
    assert decision_rule_result(mean_delta=0.02, bootstrap_lower=0.001) == "supported"
    assert decision_rule_result(mean_delta=0.019, bootstrap_lower=0.001) == "not_supported"
    assert decision_rule_result(mean_delta=0.02, bootstrap_lower=0.0) == "not_supported"
