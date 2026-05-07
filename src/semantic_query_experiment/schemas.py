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
    expected_document_ids: list[str] = Field(min_length=1)
