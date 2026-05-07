from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ExperimentConfig(BaseModel):
    """Versioned configuration for a single experiment deployment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1)
    name: str
    description: str
    random_seed: int
    target_indexed_chunks_min: int
    target_indexed_chunks_max: int
    query_rewrite_enabled: bool
    candidate_regions: list[str]


DEFAULT_CONFIG_PATH = Path("infra/config/experiment.json")
