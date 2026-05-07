from collections.abc import Sequence
from pathlib import Path

from semantic_query_experiment.data_generation.generator import generate_dataset
from semantic_query_experiment.search.embeddings import (
    EmbeddingRecord,
    build_embedded_documents,
    content_hash,
    document_embedding_text,
    embedding_hash,
)


class FakeEmbedder:
    provider = "azure-openai:text-embedding-3-large:test-deployment:2024-10-21"

    def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingRecord]:
        records: list[EmbeddingRecord] = []
        for text in texts:
            vector = [1.0, 0.0, 0.0, 0.0]
            records.append(
                EmbeddingRecord(
                    content_hash=content_hash(text),
                    model="text-embedding-3-large",
                    deployment="test-deployment",
                    api_version="2024-10-21",
                    dimensions=4,
                    embedding_hash=embedding_hash(vector),
                    vector=vector,
                    prompt_tokens=10,
                )
            )
        return records


def test_build_embedded_documents_uses_provider_sentinel_and_cache(tmp_path: Path) -> None:
    dataset = generate_dataset(requested_chunk_count=30, seed=123)
    chunks = dataset.chunks[:2]
    cache_path = tmp_path / "embedding-cache.json"

    first = build_embedded_documents(
        chunks,
        embedder=FakeEmbedder(),
        cache_path=cache_path,
        embedding_batch_size=1,
    )
    second = build_embedded_documents(
        chunks,
        embedder=FakeEmbedder(),
        cache_path=cache_path,
        embedding_batch_size=1,
    )

    assert first == second
    assert first[0]["embedding_provider"] == FakeEmbedder.provider
    assert len(first[0]["content_vector"]) == 4
    assert content_hash(document_embedding_text(chunks[0])) in cache_path.read_text()
