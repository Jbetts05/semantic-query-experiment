# Semantic Query Experiment

This repository is a reproducible experiment for evaluating the Azure AI Search
`semantic_query` parameter. The goal is to measure when separating the L1
retrieval query from the L2 semantic-ranking intent improves ranking, captions,
and answer-bearing passage selection.

Public Microsoft material documents semantic ranking and hybrid retrieval
experiments broadly. This project focuses specifically on scenarios where the
`semanticQuery` request field changes the semantic intent independently from the
base retrieval query.

![Semantic query experiment flow](assets/semantic-query-flow.animated.svg)

## What this tests

The experiment compares conventional search approaches against arms that use a
separate semantic query:

1. BM25 keyword retrieval.
2. Vector-only retrieval.
3. Hybrid retrieval.
4. Hybrid retrieval with conventional semantic ranking.
5. Hybrid retrieval with `semantic_query` controls.
6. Hybrid retrieval with deterministic separate semantic intent.
7. Hybrid retrieval with LLM-rewritten semantic intent.

The synthetic corpus uses pharmaceutical manufacturing quality and GxP
compliance documents because the domain naturally contains identifiers, jargon,
acronyms, synonyms, fielded constraints, and answer-bearing prose.

## Final experiment results

The full experiment has been run and the curated evidence bundle is tracked in
[`reports/final`](reports/final).

Key result: the strongest aggregate arm was hybrid retrieval with conventional
semantic ranking, using the same query text for retrieval and semantic ranking.
The separate rule-based `semantic_query` arm did **not** support the predefined
primary hypothesis on aggregate, but category-level analysis showed it helped
fielded/filter-style and long compliance queries while hurting identifier and
temporal queries.

Read the methodology alongside the whitepaper. The whitepaper gives the
professional narrative; [`docs/methodology.md`](docs/methodology.md) is the
important companion that defines the request shapes, metric formulas,
statistical tests, and reproduction commands.

Start with:

- [`docs/methodology.md`](docs/methodology.md) for the detailed technical
  methodology: data generation, query construction, indexing, Search request
  shapes, metrics, formulas, and reproduction commands.
- [`reports/final/whitepaper.md`](reports/final/whitepaper.md) for the
  professional summary.
- [`reports/final/report.md`](reports/final/report.md) for the concise generated
  report.
- [`reports/final/statistical-summary.json`](reports/final/statistical-summary.json)
  for the paired bootstrap CI and decision-rule result.
- [`reports/final/metrics.json`](reports/final/metrics.json) for aggregate,
  category, and per-query metrics.
- [`docs/preregistration.md`](docs/preregistration.md) for the predefined primary
  contrast and decision rule.

The raw full-run ranked results file is not committed because it is about 239 MB;
publish it as a compressed GitHub Release asset if external reviewers need the
complete record-level output.

Metric quick guide: **NDCG@10** is the primary ranking-quality metric; **NDCG@3**
is the stricter early-rank version; **MRR@10** asks how early the first exact
answer-bearing document appears; **Recall@50** checks candidate coverage;
**Hit@k** asks whether an exact answer-bearing document appears within the top
`k`; latency is directional only because the preregistered percentile protocol
was not run. The paired bootstrap CI, Wilcoxon signed-rank p-value, and primary
NDCG@10 delta are paired query-level uncertainty and effect-size views: the
delta is deterministic `semantic_query` minus identical control, the bootstrap
CI bounds uncertainty around that delta, and Wilcoxon is a secondary paired
shift test. Details are in
[`docs/methodology.md`](docs/methodology.md).

## Repository status

The current foundation includes:

- `uv` package management.
- Python source and test layout.
- schema-first artifact models.
- validation workflow scaffolding.
- read-only Azure preflight checks and Bicep infrastructure.
- deterministic synthetic data generation with hard negatives and graded labels.
- Azure AI Search indexing and query-running pipelines.
- curated final metrics, whitepaper, chart, and supporting evidence artifacts.
- initial diagrams and conventions.

No additional Azure resources are deployed without an explicit workflow-dispatch
confirmation.

## Quickstart

Install `uv`, then run:

```powershell
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Run the local CLIs:

```powershell
uv run semqry --help
uv run semqry-preflight
uv run semqry-generate-data --chunk-count 270
```

## Experiment configuration

The single experiment configuration lives at:

```text
infra/config/experiment.json
```

Local secrets and Azure resource values should be provided through environment
variables. Use `.env.example` as the template and never commit `.env`.

## Reproducibility principles

- All generated JSONL artifacts include `schema_version`.
- Random generation must accept and log a seed.
- Query arms must log request parameters, API version, region, model deployment,
  and query rewrite state.
- Reports must include raw artifacts, paired metrics, confidence intervals, and
  failure cases.
- The detailed execution methodology is maintained in
  [`docs/methodology.md`](docs/methodology.md).
- The experiment preregistration is maintained in
  [`docs/preregistration.md`](docs/preregistration.md).
- Current Azure resource names are recorded in
  [`docs/azure-resources.md`](docs/azure-resources.md).

## Diagrams

Visual assets are hand-authored SVG files under `assets/`. GitHub supports SMIL
and CSS animation in SVG, but scripts are intentionally not used.

## Teardown

Cost-bearing infrastructure for this experiment is recorded in
[`docs/azure-resources.md`](docs/azure-resources.md). Use the teardown command or
workflow only when the final artifacts you need have been preserved.
