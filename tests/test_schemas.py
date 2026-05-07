from semantic_query_experiment.schemas import ArtifactRecord, QuerySpec, SearchArm


def test_query_spec_schema_version_defaults() -> None:
    spec = QuerySpec(
        query_id="q-001",
        category="identifier",
        search_text='deviation_id:"DEV-10482" CAPA bioburden',
        semantic_intent="What CAPA prevents repeat bioburden excursions?",
        expected_document_ids=["doc-001"],
    )

    assert spec.schema_version == 1
    assert spec.expected_document_ids == ["doc-001"]


def test_artifact_record_accepts_search_arm() -> None:
    record = ArtifactRecord(
        run_id="run-001",
        arm=SearchArm.HYBRID_SEMANTIC_QUERY_DETERMINISTIC,
        query_id="q-001",
        rank=1,
        document_id="doc-001",
        score=2.75,
        metadata={"api_version": "2025-09-01"},
    )

    assert record.arm == SearchArm.HYBRID_SEMANTIC_QUERY_DETERMINISTIC
    assert record.schema_version == 1
