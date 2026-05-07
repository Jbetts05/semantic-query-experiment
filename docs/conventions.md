# Project conventions

## Package management

Use `uv` for all Python dependency and command execution:

```powershell
uv sync --locked --all-groups
uv run pytest
```

Do not install dependencies with raw `pip` unless troubleshooting an isolated
local issue.

## Schema strategy

- Use Pydantic v2 for objects that cross I/O boundaries: JSONL artifacts,
  configuration, query specs, and result records.
- Use dataclasses only for internal value objects that are not serialized.
- Include `schema_version` in every JSONL record from the start.

## Experiment environment

Use one deployment environment for the experiment. The code package environment
is the `uv`-managed Python environment.

## Secrets

Never commit secrets, `.env`, service principal credentials, model keys, or raw
Azure access tokens. Use `.env.example` for local configuration shape only.
