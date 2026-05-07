from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from semantic_query_experiment.config import (
    DEFAULT_CONFIG_PATH,
    SEARCH_FEATURE_REGIONS_PATH,
    ExperimentConfig,
    ModelTarget,
)


class CommandRunner(Protocol):
    """Runs external commands and returns parsed output."""

    def run_json(self, args: Sequence[str]) -> object:
        """Run a command and parse JSON output."""
        ...

    def run_text(self, args: Sequence[str]) -> str:
        """Run a command and return text output."""
        ...


class SubprocessCommandRunner:
    """Command runner backed by local subprocess calls."""

    def run_json(self, args: Sequence[str]) -> object:
        output = self.run_text([*args, "--output", "json"])
        return json.loads(output)

    def run_text(self, args: Sequence[str]) -> str:
        command = list(args)
        executable = shutil.which(command[0])
        if executable:
            command[0] = executable
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()


class SearchFeatureRegion(BaseModel):
    """Checked-in Search feature support for a region."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantic_ranker: bool
    query_rewrite: bool
    notes: str


class SearchFeatureAllowlist(BaseModel):
    """Search feature support sourced from Microsoft documentation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    source_url: str
    as_of: str
    regions: dict[str, SearchFeatureRegion]


class RegionCheck(BaseModel):
    """Preflight result for a single candidate region."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region: str
    search_semantic_ranker: bool = False
    search_query_rewrite: bool = False
    embedding_model_available: bool = False
    embedding_sku_available: bool = False
    generation_model_available: bool = False
    generation_sku_available: bool = False
    quota_signal_available: bool = False
    deployment_ready: bool = False
    score: int = 0
    reasons: list[str] = Field(default_factory=list)


class PreflightResult(BaseModel):
    """Structured Azure preflight output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    config_path: str
    search_feature_source_url: str
    search_feature_as_of: str
    git_commit: str | None
    az_cli_version: str | None
    subscription_id: str | None
    tenant_id: str | None
    selected_region: str | None
    regions: list[RegionCheck]
    warnings: list[str]
    result_sha256: str | None = None


@dataclass(frozen=True)
class PreflightPaths:
    """Input and output paths for preflight."""

    config_path: Path = DEFAULT_CONFIG_PATH
    search_feature_regions_path: Path = SEARCH_FEATURE_REGIONS_PATH
    output_path: Path = Path("reports/preflight/preflight-result.json")


def load_experiment_config(path: Path = DEFAULT_CONFIG_PATH) -> ExperimentConfig:
    return ExperimentConfig.model_validate_json(path.read_text(encoding="utf-8"))


def load_search_feature_allowlist(
    path: Path = SEARCH_FEATURE_REGIONS_PATH,
) -> SearchFeatureAllowlist:
    return SearchFeatureAllowlist.model_validate_json(path.read_text(encoding="utf-8"))


def run_preflight(
    *,
    paths: PreflightPaths | None = None,
    runner: CommandRunner | None = None,
) -> PreflightResult:
    """Run safe read-only Azure preflight checks."""
    resolved_paths = paths or PreflightPaths()
    command_runner = runner or SubprocessCommandRunner()
    config = load_experiment_config(resolved_paths.config_path)
    allowlist = load_search_feature_allowlist(resolved_paths.search_feature_regions_path)
    warnings: list[str] = [
        "Quota and deployable capacity are soft signals until Azure accepts the deployment.",
        "Search feature support is based on a checked-in Microsoft Learn allowlist.",
    ]

    az_cli_version = _get_az_cli_version(command_runner)
    account = _get_account(command_runner)
    subscription_id = _as_str(account.get("id"))
    tenant_id = _as_str(account.get("tenantId"))

    regions: list[RegionCheck] = []
    for region in config.candidate_regions:
        regions.append(_check_region(region, config, allowlist, command_runner))
    ranked = sorted(
        regions,
        key=lambda item: (-item.score, config.candidate_regions.index(item.region)),
    )
    selected_region = next(
        (region.region for region in ranked if region.deployment_ready),
        None,
    )

    result = PreflightResult(
        config_path=str(resolved_paths.config_path),
        search_feature_source_url=allowlist.source_url,
        search_feature_as_of=allowlist.as_of,
        git_commit=_get_git_commit(command_runner),
        az_cli_version=az_cli_version,
        subscription_id=subscription_id,
        tenant_id=tenant_id,
        selected_region=selected_region,
        regions=ranked,
        warnings=warnings,
    )
    return _with_result_hash(result)


def write_preflight_result(result: PreflightResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _check_region(
    region: str,
    config: ExperimentConfig,
    allowlist: SearchFeatureAllowlist,
    runner: CommandRunner,
) -> RegionCheck:
    reasons: list[str] = []
    feature = allowlist.regions.get(region)
    search_semantic_ranker = bool(feature and feature.semantic_ranker)
    search_query_rewrite = bool(feature and feature.query_rewrite)

    if not search_semantic_ranker:
        reasons.append("Search semantic ranker support is not listed for this region.")
    if config.query_rewrite_enabled and not search_query_rewrite:
        reasons.append("Query rewrite was requested but is not listed for this region.")

    models = _list_models(region, runner)
    embedding_model_available, embedding_sku_available = _model_and_sku_available(
        models, config.embedding_model
    )
    generation_model_available, generation_sku_available = _model_and_sku_available(
        models, config.generation_model
    )
    if not embedding_model_available:
        reasons.append(f"Embedding model {config.embedding_model.name} was not listed.")
    elif not embedding_sku_available:
        reasons.append(f"Embedding SKU {config.embedding_model.sku} was not listed.")
    if not generation_model_available:
        reasons.append(f"Generation model {config.generation_model.name} was not listed.")
    elif not generation_sku_available:
        reasons.append(f"Generation SKU {config.generation_model.sku} was not listed.")

    quota_signal_available = _has_quota_signal(region, runner)
    if not quota_signal_available:
        reasons.append(
            "No positive quota signal was available from Cognitive Services usage output."
        )

    score = sum(
        [
            search_semantic_ranker,
            not config.query_rewrite_enabled or search_query_rewrite,
            embedding_model_available,
            embedding_sku_available,
            generation_model_available,
            generation_sku_available,
            quota_signal_available,
        ]
    )
    deployment_ready = (
        search_semantic_ranker
        and (not config.query_rewrite_enabled or search_query_rewrite)
        and embedding_model_available
        and embedding_sku_available
        and generation_model_available
        and generation_sku_available
        and quota_signal_available
    )

    return RegionCheck(
        region=region,
        search_semantic_ranker=search_semantic_ranker,
        search_query_rewrite=search_query_rewrite,
        embedding_model_available=embedding_model_available,
        embedding_sku_available=embedding_sku_available,
        generation_model_available=generation_model_available,
        generation_sku_available=generation_sku_available,
        quota_signal_available=quota_signal_available,
        deployment_ready=deployment_ready,
        score=score,
        reasons=reasons,
    )


def _get_az_cli_version(runner: CommandRunner) -> str | None:
    if shutil.which("az") is None:
        return None
    try:
        version = runner.run_json(["az", "version"])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    if isinstance(version, dict):
        version_dict = cast(dict[str, object], version)
        return _as_str(version_dict.get("azure-cli"))
    return None


def _get_account(runner: CommandRunner) -> dict[str, object]:
    try:
        output = runner.run_json(["az", "account", "show"])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}
    if isinstance(output, dict):
        return cast(dict[str, object], output)
    return {}


def _get_git_commit(runner: CommandRunner) -> str | None:
    try:
        return runner.run_text(["git", "rev-parse", "HEAD"])
    except subprocess.CalledProcessError:
        return None


def _list_models(region: str, runner: CommandRunner) -> list[dict[str, object]]:
    try:
        output = runner.run_json(["az", "cognitiveservices", "model", "list", "--location", region])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []
    if isinstance(output, list):
        model_items = cast(list[object], output)
        return [cast(dict[str, object], item) for item in model_items if isinstance(item, dict)]
    return []


def _model_and_sku_available(
    models: list[dict[str, object]],
    target: ModelTarget,
) -> tuple[bool, bool]:
    model_available = False
    sku_available = False
    for model in models:
        model_name = _extract_model_name(model)
        if model_name != target.name:
            continue
        model_available = True
        skus = _extract_sku_names(model)
        if target.sku.lower() in {sku.lower() for sku in skus}:
            sku_available = True
    return model_available, sku_available


def _extract_model_name(model: dict[str, object]) -> str | None:
    direct = _as_str(model.get("name"))
    nested = model.get("model")
    nested_name = None
    if isinstance(nested, dict):
        nested_dict = cast(dict[str, object], nested)
        nested_name = _as_str(nested_dict.get("name"))
    return nested_name or direct


def _extract_sku_names(model: dict[str, object]) -> list[str]:
    raw_skus = model.get("skus")
    if not isinstance(raw_skus, list):
        return []
    names: list[str] = []
    sku_items = cast(list[object], raw_skus)
    for sku in sku_items:
        if isinstance(sku, dict):
            sku_dict = cast(dict[str, object], sku)
            name = _as_str(sku_dict.get("name"))
            if name:
                names.append(name)
    return names


def _has_quota_signal(region: str, runner: CommandRunner) -> bool:
    try:
        output = runner.run_json(["az", "cognitiveservices", "usage", "list", "--location", region])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False
    if not isinstance(output, list):
        return False
    usage_items = cast(list[object], output)
    usages = [cast(dict[str, object], item) for item in usage_items if isinstance(item, dict)]
    return any(_usage_has_available_capacity(item) for item in usages)


def _usage_has_available_capacity(item: dict[str, object]) -> bool:
    current = item.get("currentValue")
    limit = item.get("limit")
    return isinstance(current, (int, float)) and isinstance(limit, (int, float)) and limit > current


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _with_result_hash(result: PreflightResult) -> PreflightResult:
    payload = result.model_copy(update={"result_sha256": None}).model_dump_json()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return result.model_copy(update={"result_sha256": digest})
