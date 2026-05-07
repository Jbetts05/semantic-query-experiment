from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console

from semantic_query_experiment.config import load_experiment_config
from semantic_query_experiment.search.documents import FAKE_EMBEDDING_PROVIDER
from semantic_query_experiment.search.indexing import write_json
from semantic_query_experiment.search.rest import SearchRestClient
from semantic_query_experiment.search.schema import build_index_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Render or create the Azure AI Search index.")
    parser.add_argument("--endpoint", default=os.getenv("AZURE_SEARCH_ENDPOINT"))
    parser.add_argument("--admin-key", default=os.getenv("AZURE_SEARCH_ADMIN_KEY"))
    parser.add_argument("--embedding-provider", default=FAKE_EMBEDDING_PROVIDER)
    parser.add_argument(
        "--render-output",
        type=Path,
        default=Path("reports/index/index-schema.json"),
    )
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()

    config = load_experiment_config()
    schema = build_index_schema(config, embedding_provider=args.embedding_provider)
    write_json(args.render_output, schema)

    console = Console()
    console.print(f"Rendered index schema: {args.render_output}")
    console.print(f"Index name: {schema['name']}")

    if not args.create:
        return
    if not args.endpoint or not args.admin_key:
        raise SystemExit("--endpoint and --admin-key are required with --create")

    client = SearchRestClient(
        endpoint=args.endpoint,
        api_key=args.admin_key,
        api_version=config.search_api_version,
    )
    client.put_index(str(schema["name"]), schema)
    console.print("Created or updated Azure AI Search index.")
