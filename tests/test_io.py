from pathlib import Path

from semantic_query_experiment.io import read_jsonl, write_jsonl
from semantic_query_experiment.schemas import QuerySpec


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    records = [
        QuerySpec(
            query_id="q-001",
            category="synonym",
            search_text="bioburden remediation",
            semantic_intent="Which corrective action addressed contamination?",
            expected_document_ids=["doc-001"],
        )
    ]

    write_jsonl(path, records)
    loaded = read_jsonl(path, QuerySpec)

    assert loaded == records
