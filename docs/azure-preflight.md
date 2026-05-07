# Azure preflight

`uv run semqry-preflight` performs read-only checks before any deployment.

The preflight result is intentionally conservative:

- Search semantic-ranker and query-rewrite availability comes from a checked-in
  Microsoft Learn allowlist in `infra/config/search-feature-regions.json`.
- Azure OpenAI model and SKU availability is checked with Azure CLI model-list
  output when available.
- Quota and capacity are soft signals. Final capacity is only proven when Azure
  accepts the actual deployment.
- Azure Policy is best checked with deployment `what-if` against the final
  Bicep template before creating resources.

The command writes:

```text
reports/preflight/preflight-result.json
```

The result includes candidate-region rankings, `deployment_ready` flags, failure
reasons, Azure CLI version, account context, and the Git commit SHA when
available. A region is selected only when all required Search, model, SKU, and
quota-signal checks pass.
