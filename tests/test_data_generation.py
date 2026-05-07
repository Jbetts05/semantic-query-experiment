from pathlib import Path

import pytest

from semantic_query_experiment.data_generation.generator import (
    QUERY_CATEGORIES,
    GenerationPaths,
    generate_dataset,
    write_generated_dataset,
)
from semantic_query_experiment.io import read_jsonl
from semantic_query_experiment.schemas import CorpusChunk, QuerySpec, RelevanceLabel, SourceFact


def test_generation_is_deterministic() -> None:
    first = generate_dataset(requested_chunk_count=90, seed=123)
    second = generate_dataset(requested_chunk_count=90, seed=123)

    assert first.manifest.artifact_hashes == second.manifest.artifact_hashes
    assert first.queries == second.queries
    assert first.chunks == second.chunks


def test_generation_has_category_coverage_and_hard_negatives() -> None:
    dataset = generate_dataset(requested_chunk_count=270, seed=123)

    assert set(dataset.manifest.category_counts) == set(QUERY_CATEGORIES)
    assert all(count >= 10 for count in dataset.manifest.category_counts.values())
    assert dataset.manifest.hard_negative_count == dataset.manifest.query_count * 2
    assert all(len(query.hard_negative_document_ids) == 2 for query in dataset.queries)


def test_generation_emits_graded_labels() -> None:
    dataset = generate_dataset(requested_chunk_count=90, seed=123)

    labels_by_query: dict[str, list[RelevanceLabel]] = {}
    for label in dataset.labels:
        labels_by_query.setdefault(label.query_id, []).append(label)

    assert labels_by_query
    for labels in labels_by_query.values():
        assert sorted(label.relevance for label in labels) == [1, 2, 3]


def test_bm25_difficulty_gate_is_not_saturated() -> None:
    dataset = generate_dataset(requested_chunk_count=270, seed=123)

    assert 0.35 <= dataset.manifest.bm25_ndcg_at_10 <= 0.95
    assert all(
        0.05 <= score <= 1.0 for score in dataset.manifest.bm25_ndcg_at_10_by_category.values()
    )


def test_requested_chunk_count_must_cover_each_category() -> None:
    with pytest.raises(ValueError, match="one 3-document case per category"):
        generate_dataset(requested_chunk_count=12, seed=123)


def test_write_generated_dataset_round_trip(tmp_path: Path) -> None:
    dataset = generate_dataset(requested_chunk_count=90, seed=123)
    paths = GenerationPaths(
        source_facts_path=tmp_path / "source-facts.jsonl",
        chunks_path=tmp_path / "corpus-chunks.jsonl",
        queries_path=tmp_path / "query-suite.jsonl",
        labels_path=tmp_path / "relevance-labels.jsonl",
        manifest_path=tmp_path / "corpus-manifest.json",
    )

    write_generated_dataset(dataset, paths)

    assert read_jsonl(paths.source_facts_path, SourceFact) == dataset.source_facts
    assert read_jsonl(paths.chunks_path, CorpusChunk) == dataset.chunks
    assert read_jsonl(paths.queries_path, QuerySpec) == dataset.queries
    assert read_jsonl(paths.labels_path, RelevanceLabel) == dataset.labels
    assert paths.manifest_path.exists()
