from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from semantic_query_experiment.schemas import CorpusChunk
from semantic_query_experiment.search.documents import chunk_to_search_document


class EmbeddingRecord(BaseModel):
    """Cached embedding with enough metadata to detect drift."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    content_hash: str
    model: str
    deployment: str
    api_version: str
    dimensions: int
    embedding_hash: str
    vector: list[float]
    prompt_tokens: int | None = None


class EmbeddingCache(BaseModel):
    """Local embedding cache keyed by content hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    records: dict[str, EmbeddingRecord] = Field(default_factory=dict)


class Embedder(Protocol):
    """Embeds texts with metadata validation."""

    provider: str

    def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingRecord]:
        """Embed texts in order."""
        ...


class AzureOpenAIEmbedder:
    """Small Azure OpenAI embeddings REST client with bounded retries."""

    provider: str

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        expected_model: str,
        api_version: str,
        dimensions: int,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.deployment = deployment
        self.expected_model = expected_model
        self.api_version = api_version
        self.dimensions = dimensions
        self.provider = f"azure-openai:{expected_model}:{deployment}:{api_version}"

    def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingRecord]:
        payload: dict[str, object] = {"input": list(texts), "dimensions": self.dimensions}
        response = self._post_embeddings(payload)
        model = _as_str(response.get("model"))
        if model != self.expected_model:
            raise ValueError(
                f"Embedding response model {model} did not match {self.expected_model}"
            )
        response_model = self.expected_model
        usage = response.get("usage")
        prompt_tokens = None
        if isinstance(usage, dict):
            prompt_tokens = _as_int(cast(dict[str, object], usage).get("prompt_tokens"))
        raw_data = response.get("data")
        if not isinstance(raw_data, list):
            raise ValueError("Embedding response did not include a data array")

        records_by_index: dict[int, EmbeddingRecord] = {}
        for item in cast(list[object], raw_data):
            if not isinstance(item, dict):
                continue
            item_dict = cast(dict[str, object], item)
            index = _as_int(item_dict.get("index"))
            vector = item_dict.get("embedding")
            if index is None or not isinstance(vector, list):
                continue
            vector_values = [_as_float(value) for value in cast(list[object], vector)]
            if len(vector_values) != self.dimensions:
                raise ValueError(
                    f"Embedding dimensions {len(vector_values)} did not match {self.dimensions}"
                )
            text = texts[index]
            records_by_index[index] = EmbeddingRecord(
                content_hash=content_hash(text),
                model=response_model,
                deployment=self.deployment,
                api_version=self.api_version,
                dimensions=self.dimensions,
                embedding_hash=embedding_hash(vector_values),
                vector=vector_values,
                prompt_tokens=prompt_tokens,
            )

        if sorted(records_by_index) != list(range(len(texts))):
            raise ValueError("Embedding response did not contain one embedding per input")
        return [records_by_index[index] for index in range(len(texts))]

    def _post_embeddings(self, payload: dict[str, object]) -> dict[str, object]:
        url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}/embeddings"
            f"?api-version={self.api_version}"
        )
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(5):
            request = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json", "api-key": self.api_key},
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    parsed: Any = json.loads(response.read().decode("utf-8"))
                    return cast(dict[str, object], parsed)
            except urllib.error.HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 4:
                    detail = error.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Embedding request failed: {error.code} {detail}"
                    ) from error
                retry_after = error.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(delay)
        raise RuntimeError("Embedding request retries were exhausted")


def load_embedding_cache(path: Path) -> EmbeddingCache:
    if not path.exists():
        return EmbeddingCache()
    return EmbeddingCache.model_validate_json(path.read_text(encoding="utf-8"))


def write_embedding_cache(path: Path, cache: EmbeddingCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache.model_dump_json(indent=2), encoding="utf-8")


def build_embedded_documents(
    chunks: Sequence[CorpusChunk],
    *,
    embedder: Embedder,
    cache_path: Path,
    embedding_batch_size: int,
) -> list[dict[str, object]]:
    """Build documents with real embeddings, reusing cached vectors by content hash."""
    cache = load_embedding_cache(cache_path)
    documents: list[dict[str, object]] = []
    missing_texts: list[str] = []
    missing_chunks: list[CorpusChunk] = []

    for chunk in chunks:
        text = document_embedding_text(chunk)
        existing = cache.records.get(content_hash(text))
        if (
            existing
            and existing.model in embedder.provider
            and existing.deployment in embedder.provider
        ):
            documents.append(
                chunk_to_search_document(
                    chunk,
                    vector=existing.vector,
                    embedding_provider=embedder.provider,
                )
            )
            continue
        missing_texts.append(text)
        missing_chunks.append(chunk)

    for start in range(0, len(missing_texts), embedding_batch_size):
        text_batch = missing_texts[start : start + embedding_batch_size]
        chunk_batch = missing_chunks[start : start + embedding_batch_size]
        records = embedder.embed_texts(text_batch)
        for chunk, record in zip(chunk_batch, records, strict=True):
            cache.records[record.content_hash] = record
            documents.append(
                chunk_to_search_document(
                    chunk,
                    vector=record.vector,
                    embedding_provider=embedder.provider,
                )
            )
        write_embedding_cache(cache_path, cache)

    return documents


def document_embedding_text(chunk: CorpusChunk) -> str:
    return f"{chunk.title}\n{'; '.join(chunk.keywords)}\n{chunk.text}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embedding_hash(vector: Sequence[float]) -> str:
    payload = json.dumps(list(vector), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _as_float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    raise ValueError("Embedding vector contained a non-numeric value")
