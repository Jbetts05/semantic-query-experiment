from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from semantic_query_experiment.search.rest import SearchRestClient


class UploadCheckpoint(BaseModel):
    """Per-document upload checkpoint for resumable indexing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    succeeded_document_ids: set[str] = Field(default_factory=set)


def load_checkpoint(path: Path) -> UploadCheckpoint:
    if not path.exists():
        return UploadCheckpoint()
    return UploadCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))


def write_checkpoint(path: Path, checkpoint: UploadCheckpoint) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")


def batch_documents(
    documents: Iterable[dict[str, object]],
    *,
    batch_size: int,
    checkpoint: UploadCheckpoint | None = None,
) -> list[list[dict[str, object]]]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    succeeded: set[str] = checkpoint.succeeded_document_ids if checkpoint else set()
    pending = [document for document in documents if str(document["id"]) not in succeeded]
    return [pending[index : index + batch_size] for index in range(0, len(pending), batch_size)]


def upload_documents_resumable(
    *,
    client: SearchRestClient,
    index_name: str,
    documents: list[dict[str, object]],
    checkpoint_path: Path,
    batch_size: int = 500,
) -> UploadCheckpoint:
    checkpoint = load_checkpoint(checkpoint_path)
    for batch in batch_documents(documents, batch_size=batch_size, checkpoint=checkpoint):
        response = client.upload_documents(index_name, batch)
        succeeded_ids = _successful_document_ids(response)
        expected_ids = {str(document["id"]) for document in batch}
        failed_ids = expected_ids - succeeded_ids
        if failed_ids:
            raise RuntimeError(f"Search upload failed for document ids: {sorted(failed_ids)}")
        checkpoint = checkpoint.model_copy(
            update={"succeeded_document_ids": checkpoint.succeeded_document_ids | succeeded_ids}
        )
        write_checkpoint(checkpoint_path, checkpoint)
    return checkpoint


def validate_documents(
    documents: list[dict[str, object]],
    *,
    dimensions: int,
    embedding_provider: str,
) -> None:
    for document in documents:
        vector = document.get("content_vector")
        if not isinstance(vector, list):
            raise ValueError(f"Document {document.get('id')} has invalid vector dimensions")
        vector_values = cast(list[object], vector)
        if len(vector_values) != dimensions:
            raise ValueError(f"Document {document.get('id')} has invalid vector dimensions")
        if document.get("embedding_provider") != embedding_provider:
            raise ValueError(f"Document {document.get('id')} has invalid embedding provider")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _successful_document_ids(response: dict[str, object]) -> set[str]:
    raw_values = response.get("value")
    if not isinstance(raw_values, list):
        return set()
    succeeded: set[str] = set()
    values = cast(list[object], raw_values)
    for value in values:
        if not isinstance(value, dict):
            continue
        value_dict = cast(dict[str, object], value)
        key = value_dict.get("key")
        status = value_dict.get("status")
        if isinstance(key, str) and status is True:
            succeeded.add(key)
    return succeeded
