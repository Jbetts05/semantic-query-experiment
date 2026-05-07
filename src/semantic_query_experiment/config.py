from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelTarget(BaseModel):
    """Model deployment target used during region preflight."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    sku: str
    deployment_name: str
    capacity: int = Field(ge=1)
    dimensions: int | None = None


class ExperimentConfig(BaseModel):
    """Versioned configuration for a single experiment deployment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    name: str
    description: str
    random_seed: int
    target_indexed_chunks_min: int
    target_indexed_chunks_max: int
    query_rewrite_enabled: bool
    search_api_version: str
    search_sku: str
    search_index_base_name: str
    search_semantic_configuration: str
    embedding_model: ModelTarget
    generation_model: ModelTarget
    candidate_regions: list[str]


DEFAULT_CONFIG_PATH = Path("infra/config/experiment.json")
SEARCH_FEATURE_REGIONS_PATH = Path("infra/config/search-feature-regions.json")


def load_experiment_config(path: Path = DEFAULT_CONFIG_PATH) -> ExperimentConfig:
    return ExperimentConfig.model_validate_json(path.read_text(encoding="utf-8"))
