from __future__ import annotations

import hashlib
import json

from semantic_query_experiment.config import ExperimentConfig

TEXT_ANALYZER = "en.microsoft"
IDENTIFIER_ANALYZER = "keyword"
VECTOR_PROFILE = "hnsw-cosine-profile"
VECTOR_ALGORITHM = "hnsw-cosine"
EMBEDDING_PROVIDER_FIELD = "embedding_provider"


def build_index_schema(config: ExperimentConfig, *, embedding_provider: str) -> dict[str, object]:
    """Build the Azure AI Search index schema used by all experiment arms."""
    dimensions = config.embedding_model.dimensions
    if dimensions is None:
        raise ValueError("embedding_model.dimensions is required for index schema generation")

    schema_without_name: dict[str, object] = {
        "fields": [
            _simple_field("id", key=True, filterable=True, sortable=True),
            _simple_field("document_id", filterable=True, sortable=True),
            _searchable_field("document_id_text", analyzer=IDENTIFIER_ANALYZER),
            _simple_field("chunk_id", filterable=True, sortable=True),
            _searchable_field("chunk_id_text", analyzer=IDENTIFIER_ANALYZER),
            _searchable_field("title", analyzer=TEXT_ANALYZER),
            _simple_field("doc_type", filterable=True, facetable=True, sortable=True),
            _searchable_field("doc_type_text", analyzer=IDENTIFIER_ANALYZER),
            _simple_field("product", filterable=True, facetable=True, sortable=True),
            _searchable_field("product_text", analyzer=TEXT_ANALYZER),
            _simple_field("site", filterable=True, facetable=True, sortable=True),
            _searchable_field("site_text", analyzer=TEXT_ANALYZER),
            _simple_field("batch_id", filterable=True, sortable=True),
            _searchable_field("batch_id_text", analyzer=IDENTIFIER_ANALYZER),
            _simple_field("deviation_id", filterable=True, sortable=True),
            _searchable_field("deviation_id_text", analyzer=IDENTIFIER_ANALYZER),
            _simple_field("sop_id", filterable=True, sortable=True),
            _searchable_field("sop_id_text", analyzer=IDENTIFIER_ANALYZER),
            _collection_field("keywords", searchable=True, filterable=True, analyzer=TEXT_ANALYZER),
            _searchable_field("text", analyzer=TEXT_ANALYZER),
            _collection_field("source_fact_ids", filterable=True),
            _collection_field("expected_answer_spans", searchable=True, analyzer=TEXT_ANALYZER),
            _simple_field("is_hard_negative", field_type="Edm.Boolean", filterable=True),
            _collection_field("hard_negative_for_query_ids", filterable=True),
            _simple_field(EMBEDDING_PROVIDER_FIELD, filterable=True, facetable=True),
            {
                "name": "content_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": False,
                "dimensions": dimensions,
                "vectorSearchProfile": VECTOR_PROFILE,
            },
        ],
        "vectorSearch": {
            "algorithms": [
                {
                    "name": VECTOR_ALGORITHM,
                    "kind": "hnsw",
                    "hnswParameters": {
                        "metric": "cosine",
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                    },
                }
            ],
            "profiles": [
                {
                    "name": VECTOR_PROFILE,
                    "algorithm": VECTOR_ALGORITHM,
                }
            ],
        },
        "semantic": {
            "configurations": [
                {
                    "name": config.search_semantic_configuration,
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "prioritizedContentFields": [{"fieldName": "text"}],
                        "prioritizedKeywordsFields": [
                            {"fieldName": "keywords"},
                            {"fieldName": "doc_type_text"},
                            {"fieldName": "product_text"},
                            {"fieldName": "site_text"},
                        ],
                    },
                }
            ]
        },
        "scoringProfiles": [],
        "suggesters": [],
        "corsOptions": None,
        "encryptionKey": None,
    }
    schema_hash = search_schema_hash(schema_without_name)
    return {
        "name": index_name(config, embedding_provider=embedding_provider, schema_hash=schema_hash),
        **schema_without_name,
    }


def index_name(
    config: ExperimentConfig,
    *,
    embedding_provider: str,
    schema_hash: str | None = None,
) -> str:
    """Create a stable index name that changes for incompatible schema/provider changes."""
    provider_slug = _slug(embedding_provider)
    hash_part = schema_hash or search_schema_hash(
        build_index_schema(config, embedding_provider=embedding_provider)
    )
    return (
        f"{config.search_index_base_name}-{hash_part[:8]}-"
        f"{provider_slug}-{config.embedding_model.dimensions}"
    )


def search_schema_hash(schema: dict[str, object]) -> str:
    """Hash schema-defining settings, excluding the index name."""
    normalized = {key: value for key, value in schema.items() if key != "name"}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _simple_field(
    name: str,
    *,
    field_type: str = "Edm.String",
    key: bool = False,
    filterable: bool = False,
    sortable: bool = False,
    facetable: bool = False,
) -> dict[str, object]:
    return {
        "name": name,
        "type": field_type,
        "key": key,
        "searchable": False,
        "filterable": filterable,
        "sortable": sortable,
        "facetable": facetable,
        "retrievable": True,
    }


def _searchable_field(name: str, *, analyzer: str) -> dict[str, object]:
    return {
        "name": name,
        "type": "Edm.String",
        "key": False,
        "searchable": True,
        "filterable": False,
        "sortable": False,
        "facetable": False,
        "retrievable": True,
        "analyzer": analyzer,
    }


def _collection_field(
    name: str,
    *,
    searchable: bool = False,
    filterable: bool = False,
    analyzer: str | None = None,
) -> dict[str, object]:
    field: dict[str, object] = {
        "name": name,
        "type": "Collection(Edm.String)",
        "searchable": searchable,
        "filterable": filterable,
        "sortable": False,
        "facetable": False,
        "retrievable": True,
    }
    if analyzer:
        field["analyzer"] = analyzer
    return field


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value.lower()).strip(
        "-"
    )
