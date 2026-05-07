from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence

from semantic_query_experiment.schemas import CorpusChunk
from semantic_query_experiment.search.schema import EMBEDDING_PROVIDER_FIELD

FAKE_EMBEDDING_PROVIDER = "fake-v1"


def chunk_to_search_document(
    chunk: CorpusChunk,
    *,
    vector: Sequence[float],
    embedding_provider: str,
) -> dict[str, object]:
    """Convert a corpus chunk to the JSON shape uploaded to Azure AI Search."""
    return {
        "id": chunk.document_id,
        "document_id": chunk.document_id,
        "document_id_text": chunk.document_id,
        "chunk_id": chunk.chunk_id,
        "chunk_id_text": chunk.chunk_id,
        "title": chunk.title,
        "doc_type": chunk.doc_type,
        "doc_type_text": chunk.doc_type,
        "product": chunk.product,
        "product_text": chunk.product,
        "site": chunk.site,
        "site_text": chunk.site,
        "batch_id": chunk.batch_id,
        "batch_id_text": chunk.batch_id,
        "deviation_id": chunk.deviation_id,
        "deviation_id_text": chunk.deviation_id,
        "sop_id": chunk.sop_id,
        "sop_id_text": chunk.sop_id,
        "keywords": chunk.keywords,
        "text": chunk.text,
        "source_fact_ids": chunk.source_fact_ids,
        "expected_answer_spans": chunk.expected_answer_spans,
        "is_hard_negative": chunk.is_hard_negative,
        "hard_negative_for_query_ids": chunk.hard_negative_for_query_ids,
        EMBEDDING_PROVIDER_FIELD: embedding_provider,
        "content_vector": list(vector),
    }


def fake_embedding(text: str, *, dimensions: int) -> list[float]:
    """Deterministic local embedding for schema and batching tests only."""
    if dimensions < 1:
        raise ValueError("dimensions must be positive")
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
        for byte in digest:
            values.append((byte / 255.0) - 0.5)
            if len(values) == dimensions:
                break
        counter += 1
    magnitude = math.sqrt(sum(value * value for value in values))
    return [value / magnitude for value in values]


def build_fake_documents(
    chunks: Iterable[CorpusChunk],
    *,
    dimensions: int,
) -> list[dict[str, object]]:
    """Build fake-vector documents for dry runs and unit tests."""
    return [
        chunk_to_search_document(
            chunk,
            vector=fake_embedding(f"{chunk.title}\n{chunk.text}", dimensions=dimensions),
            embedding_provider=FAKE_EMBEDDING_PROVIDER,
        )
        for chunk in chunks
    ]
