from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

import jsonlines
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def write_jsonl(path: Path, records: Iterable[BaseModel]) -> None:
    """Write Pydantic models as JSONL records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with jsonlines.open(path, mode="w") as writer:
        for record in records:
            writer.write(record.model_dump(mode="json"))


def read_jsonl(path: Path, model_type: type[ModelT]) -> list[ModelT]:
    """Read JSONL records into Pydantic models."""
    with jsonlines.open(path, mode="r") as reader:
        return [model_type.model_validate(row) for row in reader]
