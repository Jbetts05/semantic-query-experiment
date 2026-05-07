from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JsonScalar = str | int | float | bool | None
JsonObject = dict[str, JsonScalar]


class SearchArm(StrEnum):
    """Experiment arms for search comparisons."""

    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"
    HYBRID_SEMANTIC = "hybrid_semantic"
    HYBRID_SEMANTIC_QUERY_CONTROL = "hybrid_semantic_query_control"
    HYBRID_SEMANTIC_QUERY_DETERMINISTIC = "hybrid_semantic_query_deterministic"
    HYBRID_SEMANTIC_QUERY_LLM = "hybrid_semantic_query_llm"


class ArtifactRecord(BaseModel):
    """A single ranked result emitted by an experiment arm."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str
    arm: SearchArm
    query_id: str
    rank: int = Field(ge=1)
    document_id: str
    score: float | None = None
    metadata: JsonObject = Field(default_factory=dict)


class QuerySpec(BaseModel):
    """A query and its expected relevant documents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    query_id: str
    category: str
    search_text: str
    semantic_intent: str
    semantic_query_derivation: Literal["identical", "deterministic", "llm"] = "deterministic"
    expected_document_ids: list[str] = Field(min_length=1)
    hard_negative_document_ids: list[str] = Field(default_factory=list)
    filters: JsonObject = Field(default_factory=dict)


class SourceFact(BaseModel):
    """Structured fact used to generate a synthetic corpus chunk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    fact_id: str
    gold_document_id: str
    product: str
    site: str
    doc_type: str
    primary_identifier: str
    secondary_identifier: str
    jargon_term: str
    plain_language_term: str
    answer: str
    effective_date: str
    superseded_identifier: str


class CorpusChunk(BaseModel):
    """Pre-chunked synthetic document row for Azure AI Search indexing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    document_id: str
    chunk_id: str
    title: str
    doc_type: str
    product: str
    site: str
    batch_id: str | None = None
    deviation_id: str | None = None
    sop_id: str | None = None
    keywords: list[str]
    text: str
    source_fact_ids: list[str]
    expected_answer_spans: list[str] = Field(default_factory=list)
    is_hard_negative: bool = False
    hard_negative_for_query_ids: list[str] = Field(default_factory=list)


class RelevanceLabel(BaseModel):
    """Graded relevance label for a generated query/document pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    query_id: str
    document_id: str
    relevance: int = Field(ge=0, le=3)
    label_source: Literal["generator_fact_coverage"] = "generator_fact_coverage"
    rationale: str


class CorpusManifest(BaseModel):
    """Summary metadata emitted with generated synthetic artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    seed: int
    requested_chunk_count: int
    actual_chunk_count: int
    query_count: int
    source_fact_count: int
    category_counts: dict[str, int]
    hard_negative_count: int
    bm25_ndcg_at_10: float
    bm25_ndcg_at_10_by_category: dict[str, float]
    artifact_hashes: dict[str, str]
