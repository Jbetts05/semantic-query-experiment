from semantic_query_experiment.config import load_experiment_config
from semantic_query_experiment.data_generation.generator import generate_dataset
from semantic_query_experiment.search.documents import FAKE_EMBEDDING_PROVIDER, build_fake_documents
from semantic_query_experiment.search.indexing import (
    UploadCheckpoint,
    batch_documents,
    validate_documents,
)
from semantic_query_experiment.search.schema import build_index_schema


def test_index_schema_pins_identifier_and_text_analyzers() -> None:
    schema = build_index_schema(
        load_experiment_config(),
        embedding_provider=FAKE_EMBEDDING_PROVIDER,
    )
    fields = {str(field["name"]): field for field in schema["fields"]}  # type: ignore[index]

    assert fields["deviation_id"]["searchable"] is False
    assert fields["deviation_id"]["filterable"] is True
    assert fields["deviation_id_text"]["analyzer"] == "keyword"
    assert fields["text"]["analyzer"] == "en.microsoft"


def test_index_schema_matches_semantic_configuration_and_vector_dimensions() -> None:
    config = load_experiment_config()
    schema = build_index_schema(config, embedding_provider=FAKE_EMBEDDING_PROVIDER)

    vector_field = next(field for field in schema["fields"] if field["name"] == "content_vector")  # type: ignore[index]
    semantic = schema["semantic"]  # type: ignore[index]
    configuration = semantic["configurations"][0]  # type: ignore[index]
    prioritized = configuration["prioritizedFields"]

    assert vector_field["dimensions"] == config.embedding_model.dimensions
    assert configuration["name"] == config.search_semantic_configuration
    assert prioritized["titleField"]["fieldName"] == "title"
    assert prioritized["prioritizedContentFields"] == [{"fieldName": "text"}]
    assert {"fieldName": "keywords"} in prioritized["prioritizedKeywordsFields"]


def test_fake_documents_include_provider_sentinel_and_valid_vector_dimensions() -> None:
    dataset = generate_dataset(requested_chunk_count=30, seed=123)
    documents = build_fake_documents(dataset.chunks, dimensions=32)

    validate_documents(
        documents,
        dimensions=32,
        embedding_provider=FAKE_EMBEDDING_PROVIDER,
    )
    assert documents[0]["embedding_provider"] == FAKE_EMBEDDING_PROVIDER
    assert len(documents[0]["content_vector"]) == 32


def test_batch_documents_respects_per_document_checkpoint() -> None:
    documents = [{"id": f"doc-{index}"} for index in range(5)]
    checkpoint = UploadCheckpoint(succeeded_document_ids={"doc-1", "doc-3"})

    batches = batch_documents(documents, batch_size=2, checkpoint=checkpoint)

    assert batches == [[{"id": "doc-0"}, {"id": "doc-2"}], [{"id": "doc-4"}]]
