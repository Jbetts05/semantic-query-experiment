import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel


def write_jsonl(path: Path, records: Iterable[BaseModel]) -> None:
    """Write Pydantic models as JSONL records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as writer:
        for record in records:
            writer.write(record.model_dump_json())
            writer.write("\n")


def read_jsonl[ModelT: BaseModel](path: Path, model_type: type[ModelT]) -> list[ModelT]:
    """Read JSONL records into Pydantic models."""
    rows: list[ModelT] = []
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if line.strip():
                rows.append(model_type.model_validate(json.loads(line)))
    return rows
