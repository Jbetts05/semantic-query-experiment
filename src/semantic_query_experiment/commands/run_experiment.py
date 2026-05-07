from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console

from semantic_query_experiment.config import load_experiment_config
from semantic_query_experiment.io import read_jsonl, write_jsonl
from semantic_query_experiment.schemas import QuerySpec
from semantic_query_experiment.search.embeddings import AzureOpenAIEmbedder
from semantic_query_experiment.search.query import DEFAULT_ARMS, ExperimentRunner
from semantic_query_experiment.search.rest import SearchRestClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pinned Azure AI Search experiment arms.")
    parser.add_argument("--queries", type=Path, default=Path("data/queries/query-suite.jsonl"))
    parser.add_argument("--run-id", default="full-suite")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/runs/full-suite/results.jsonl"),
    )
    parser.add_argument("--search-endpoint", default=os.getenv("AZURE_SEARCH_ENDPOINT"))
    parser.add_argument("--search-admin-key", default=os.getenv("AZURE_SEARCH_ADMIN_KEY"))
    parser.add_argument("--azure-openai-endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument("--azure-openai-key", default=os.getenv("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--azure-openai-api-version", default="2024-10-21")
    parser.add_argument("--query-embedding-batch-size", type=int, default=16)
    args = parser.parse_args()

    if not args.search_endpoint or not args.search_admin_key:
        raise SystemExit("--search-endpoint and --search-admin-key are required")
    if not args.azure_openai_endpoint or not args.azure_openai_key:
        raise SystemExit("--azure-openai-endpoint and --azure-openai-key are required")

    config = load_experiment_config()
    dimensions = config.embedding_model.dimensions
    if dimensions is None:
        raise SystemExit("embedding_model.dimensions is required")

    queries = read_jsonl(args.queries, QuerySpec)
    if args.limit is not None:
        queries = queries[: args.limit]

    search_client = SearchRestClient(
        endpoint=args.search_endpoint,
        api_key=args.search_admin_key,
        api_version=config.search_api_version,
    )
    embedder = AzureOpenAIEmbedder(
        endpoint=args.azure_openai_endpoint,
        api_key=args.azure_openai_key,
        deployment=config.embedding_model.deployment_name,
        expected_model=config.embedding_model.name,
        api_version=args.azure_openai_api_version,
        dimensions=dimensions,
    )
    runner = ExperimentRunner(
        config=config,
        search_client=search_client,
        embedder=embedder,
        run_id=args.run_id,
        query_embedding_batch_size=args.query_embedding_batch_size,
    )
    records = runner.run_queries(queries, arms=DEFAULT_ARMS)
    write_jsonl(args.output, records)

    console = Console()
    console.print(f"Ran {len(queries)} queries across {len(DEFAULT_ARMS)} arms.")
    console.print(f"Wrote {len(records)} result records to {args.output}.")
