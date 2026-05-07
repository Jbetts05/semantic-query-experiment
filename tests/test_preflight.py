from collections.abc import Sequence
from pathlib import Path

from semantic_query_experiment.azure.preflight import (
    PreflightPaths,
    run_preflight,
    write_preflight_result,
)


class FakeRunner:
    def run_json(self, args: Sequence[str]) -> object:
        command = " ".join(args)
        if command == "az version":
            return {"azure-cli": "2.99.0"}
        if command == "az account show":
            return {"id": "sub-123", "tenantId": "tenant-123"}
        if "cognitiveservices model list" in command:
            return [
                {
                    "model": {"name": "text-embedding-3-large"},
                    "skus": [{"name": "Standard"}],
                },
                {
                    "model": {"name": "gpt-5.5"},
                    "skus": [{"name": "GlobalStandard"}],
                },
            ]
        if "cognitiveservices usage list" in command:
            return [{"currentValue": 0, "limit": 10}]
        raise AssertionError(f"Unexpected JSON command: {command}")

    def run_text(self, args: Sequence[str]) -> str:
        command = " ".join(args)
        if command == "git rev-parse HEAD":
            return "abc123"
        raise AssertionError(f"Unexpected text command: {command}")


def test_preflight_selects_supported_region(tmp_path: Path) -> None:
    paths = PreflightPaths(output_path=tmp_path / "preflight-result.json")

    result = run_preflight(paths=paths, runner=FakeRunner())
    write_preflight_result(result, paths.output_path)

    assert result.selected_region == "eastus2"
    assert result.subscription_id == "sub-123"
    assert result.result_sha256 is not None
    assert paths.output_path.exists()
