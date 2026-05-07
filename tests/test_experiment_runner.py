from collections.abc import Sequence

from semantic_query_experiment.config import load_experiment_config
from semantic_query_experiment.evaluation import evaluate_results
from semantic_query_experiment.schemas import QuerySpec, RelevanceLabel, SearchArm
from semantic_query_experiment.search.embeddings import (
    EmbeddingRecord,
    content_hash,
    embedding_hash,
)
from semantic_query_experiment.search.query import ExperimentRunner


class FakeSearchClient:
    def search_documents(self, index_name: str, payload: dict[str, object]) -> dict[str, object]:
        del index_name, payload
        return {
            "value": [
                {"document_id": "doc-1", "@search.score": 2.0},
                {"document_id": "doc-2", "@search.score": 1.0},
            ]
        }


class FakeEmbedder:
    provider = "azure-openai:text-embedding-3-large:test:2024-10-21"

    def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingRecord]:
        vector = [1.0, 0.0, 0.0, 0.0]
        return [
            EmbeddingRecord(
                content_hash=content_hash(text),
                model="text-embedding-3-large",
                deployment="test",
                api_version="2024-10-21",
                dimensions=4,
                embedding_hash=embedding_hash(vector),
                vector=vector,
            )
            for text in texts
        ]


def test_experiment_runner_and_evaluation() -> None:
    query = QuerySpec(
        query_id="q-1",
        category="id_lookup",
        search_text="DEV-1 CAPA",
        semantic_intent="What action resolved DEV-1?",
        expected_document_ids=["doc-1"],
    )
    runner = ExperimentRunner(
        config=load_experiment_config(),
        search_client=FakeSearchClient(),  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        run_id="test-run",
        query_embedding_batch_size=1,
    )

    records = runner.run_queries(
        [query],
        arms=[
            SearchArm.HYBRID_SEMANTIC_QUERY_CONTROL,
            SearchArm.HYBRID_SEMANTIC_QUERY_DETERMINISTIC,
        ],
    )
    metrics = evaluate_results(
        queries=[query],
        labels=[
            RelevanceLabel(
                query_id="q-1",
                document_id="doc-1",
                relevance=3,
                rationale="Gold document.",
            )
        ],
        records=records,
    )

    assert len(records) == 4
    assert metrics["query_count"] == 1
    assert metrics["primary_delta"] == {
        "query_count": 1,
        "mean_delta_ndcg_at_10": 0.0,
    }
