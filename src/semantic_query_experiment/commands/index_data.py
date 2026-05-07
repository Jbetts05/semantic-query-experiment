from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console

from semantic_query_experiment.config import load_experiment_config
from semantic_query_experiment.io import read_jsonl
from semantic_query_experiment.schemas import CorpusChunk
from semantic_query_experiment.search.documents import FAKE_EMBEDDING_PROVIDER, build_fake_documents
from semantic_query_experiment.search.embeddings import (
    AzureOpenAIEmbedder,
    build_embedded_documents,
)
from semantic_query_experiment.search.indexing import (
    upload_documents_resumable,
    validate_documents,
    validate_live_index_schema,
    write_json,
)
from semantic_query_experiment.search.rest import SearchRestClient
from semantic_query_experiment.search.schema import build_index_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or upload Azure AI Search documents.")
    parser.add_argument("--chunks", type=Path, default=Path("data/generated/corpus-chunks.jsonl"))
    parser.add_argument("--endpoint", default=os.getenv("AZURE_SEARCH_ENDPOINT"))
    parser.add_argument("--admin-key", default=os.getenv("AZURE_SEARCH_ADMIN_KEY"))
    parser.add_argument("--embedding-mode", choices=["fake", "azure-openai"], default="fake")
    parser.add_argument("--azure-openai-endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument("--azure-openai-key", default=os.getenv("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--azure-openai-api-version", default="2024-10-21")
    parser.add_argument("--azure-openai-deployment", default=None)
    parser.add_argument("--embedding-batch-size", type=int, default=16)
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=Path("reports/index/embedding-cache.json"),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--dry-run-output",
        type=Path,
        default=Path("reports/index/documents-preview.json"),
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("reports/index/upload-checkpoint.json"),
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--allow-fake-upload", action="store_true")
    args = parser.parse_args()

    config = load_experiment_config()
    dimensions = config.embedding_model.dimensions
    if dimensions is None:
        raise SystemExit("embedding_model.dimensions is required")

    chunks = read_jsonl(args.chunks, CorpusChunk)
    if args.limit is not None:
        chunks = chunks[: args.limit]
    if args.embedding_mode == "fake":
        embedding_provider = FAKE_EMBEDDING_PROVIDER
        documents = build_fake_documents(chunks, dimensions=dimensions)
    else:
        deployment = args.azure_openai_deployment or config.embedding_model.deployment_name
        if not args.azure_openai_endpoint or not args.azure_openai_key:
            raise SystemExit(
                "--azure-openai-endpoint and --azure-openai-key are required "
                "with --embedding-mode azure-openai"
            )
        embedder = AzureOpenAIEmbedder(
            endpoint=args.azure_openai_endpoint,
            api_key=args.azure_openai_key,
            deployment=deployment,
            expected_model=config.embedding_model.name,
            api_version=args.azure_openai_api_version,
            dimensions=dimensions,
        )
        embedding_provider = embedder.provider
        documents = build_embedded_documents(
            chunks,
            embedder=embedder,
            cache_path=args.embedding_cache,
            embedding_batch_size=args.embedding_batch_size,
        )
    validate_documents(
        documents,
        dimensions=dimensions,
        embedding_provider=embedding_provider,
    )
    write_json(
        args.dry_run_output,
        {"document_count": len(documents), "preview": documents[:3]},
    )

    console = Console()
    console.print(f"Prepared {len(documents)} documents.")
    console.print(f"Wrote dry-run preview: {args.dry_run_output}")

    if not args.upload:
        return
    if embedding_provider == FAKE_EMBEDDING_PROVIDER and not args.allow_fake_upload:
        raise SystemExit("Refusing to upload fake embeddings without --allow-fake-upload")
    if not args.endpoint or not args.admin_key:
        raise SystemExit("--endpoint and --admin-key are required with --upload")

    schema = build_index_schema(config, embedding_provider=embedding_provider)
    client = SearchRestClient(
        endpoint=args.endpoint,
        api_key=args.admin_key,
        api_version=config.search_api_version,
    )
    validate_live_index_schema(client.get_index(str(schema["name"])), dimensions=dimensions)
    checkpoint = upload_documents_resumable(
        client=client,
        index_name=str(schema["name"]),
        documents=documents,
        checkpoint_path=args.checkpoint,
        batch_size=args.batch_size,
    )
    console.print(f"Uploaded {len(checkpoint.succeeded_document_ids)} documents.")
