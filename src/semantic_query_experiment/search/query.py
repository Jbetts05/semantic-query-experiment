from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from semantic_query_experiment.config import ExperimentConfig
from semantic_query_experiment.schemas import ArtifactRecord, QuerySpec, SearchArm
from semantic_query_experiment.search.embeddings import Embedder
from semantic_query_experiment.search.rest import SearchRestClient
from semantic_query_experiment.search.schema import build_index_schema

RESULT_TOP = 50
VECTOR_K = 50

DEFAULT_ARMS: tuple[SearchArm, ...] = (
    SearchArm.BM25,
    SearchArm.VECTOR,
    SearchArm.HYBRID,
    SearchArm.HYBRID_SEMANTIC,
    SearchArm.HYBRID_SEMANTIC_QUERY_CONTROL,
    SearchArm.HYBRID_SEMANTIC_QUERY_DETERMINISTIC,
)


@dataclass(frozen=True)
class ExperimentRunner:
    """Runs pinned Azure AI Search experiment arms for query specs."""

    config: ExperimentConfig
    search_client: SearchRestClient
    embedder: Embedder
    run_id: str
    query_embedding_batch_size: int = 16

    def run_queries(
        self,
        queries: Sequence[QuerySpec],
        *,
        arms: Sequence[SearchArm] = DEFAULT_ARMS,
    ) -> list[ArtifactRecord]:
        records: list[ArtifactRecord] = []
        index_name = str(
            build_index_schema(self.config, embedding_provider=self.embedder.provider)["name"]
        )
        query_vectors = self._embed_query_vectors(queries)
        for query in queries:
            vector = query_vectors[query.query_id]
            for arm in arms:
                payload = self._payload_for_arm(query, arm, vector)
                started = time.perf_counter()
                response = self.search_client.search_documents(index_name, payload)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                records.extend(
                    self._records_from_response(
                        response,
                        query=query,
                        arm=arm,
                        elapsed_ms=elapsed_ms,
                    )
                )
        return records

    def _embed_query_vectors(self, queries: Sequence[QuerySpec]) -> dict[str, list[float]]:
        vectors: dict[str, list[float]] = {}
        for start in range(0, len(queries), self.query_embedding_batch_size):
            query_batch = queries[start : start + self.query_embedding_batch_size]
            embeddings = self.embedder.embed_texts([query.search_text for query in query_batch])
            vectors.update(
                {
                    query.query_id: embedding.vector
                    for query, embedding in zip(query_batch, embeddings, strict=True)
                }
            )
        return vectors

    def _payload_for_arm(
        self,
        query: QuerySpec,
        arm: SearchArm,
        vector: list[float],
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "top": RESULT_TOP,
            "select": "document_id",
            "count": False,
        }
        filter_expression = _filter_expression(query)
        if filter_expression:
            payload["filter"] = filter_expression

        if arm == SearchArm.BM25:
            payload["search"] = query.search_text
            return payload

        if arm == SearchArm.VECTOR:
            payload["search"] = "*"
            payload["vectorQueries"] = [_vector_query(vector)]
            return payload

        payload["search"] = query.search_text
        payload["vectorQueries"] = [_vector_query(vector)]

        if arm == SearchArm.HYBRID:
            return payload

        payload["queryType"] = "semantic"
        payload["semanticConfiguration"] = self.config.search_semantic_configuration
        if arm == SearchArm.HYBRID_SEMANTIC_QUERY_CONTROL:
            payload["semanticQuery"] = query.search_text
        elif arm == SearchArm.HYBRID_SEMANTIC_QUERY_DETERMINISTIC:
            payload["semanticQuery"] = query.semantic_intent
        return payload

    def _records_from_response(
        self,
        response: dict[str, object],
        *,
        query: QuerySpec,
        arm: SearchArm,
        elapsed_ms: int,
    ) -> list[ArtifactRecord]:
        raw_values = response.get("value")
        if not isinstance(raw_values, list):
            return []
        records: list[ArtifactRecord] = []
        for rank, raw_result in enumerate(cast(list[object], raw_values), start=1):
            if not isinstance(raw_result, dict):
                continue
            result = cast(dict[str, object], raw_result)
            document_id = _as_str(result.get("document_id"))
            if not document_id:
                continue
            records.append(
                ArtifactRecord(
                    run_id=self.run_id,
                    arm=arm,
                    query_id=query.query_id,
                    rank=rank,
                    document_id=document_id,
                    score=_as_float(result.get("@search.score")),
                    metadata={
                        "category": query.category,
                        "elapsed_ms": elapsed_ms,
                        "api_version": self.config.search_api_version,
                    },
                )
            )
        return records


def _vector_query(vector: list[float]) -> dict[str, object]:
    return {
        "kind": "vector",
        "vector": vector,
        "fields": "content_vector",
        "k": VECTOR_K,
    }


def _filter_expression(query: QuerySpec) -> str | None:
    clauses: list[str] = []
    for field in ("product", "site", "doc_type"):
        value = query.filters.get(field)
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            clauses.append(f"{field} eq '{escaped}'")
    return " and ".join(clauses) if clauses else None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None
