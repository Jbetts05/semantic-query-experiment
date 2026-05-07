# Final experiment evidence bundle

This folder contains the curated publication package for the Azure AI Search
`semantic_query` comparison experiment. It is intentionally smaller than the full
local run directory so the GitHub repository can be the source of truth for the
whitepaper without committing transient caches or very large raw result dumps.

## Included artifacts

| Artifact | Description |
| --- | --- |
| `whitepaper.md` | Professional summary of the experiment, findings, caveats, and recommended interpretation. |
| `report.md` | Machine-generated concise report from the final metrics bundle. |
| `metrics.json` | Aggregate, category-level, and per-query metric summaries derived from the full run. |
| `statistical-summary.json` | Auditable paired bootstrap CI, category counts, primary decision result, and preregistration commit references. |
| `run-manifest.json` | Run ID, preregistration commits, Azure resources, commands, artifact paths, and run scale. |
| `ndcg-at-10.svg` | NDCG@10 chart used by the report. |

## Supporting tracked artifacts

| Artifact | Description |
| --- | --- |
| `../../docs/methodology.md` | Detailed methodology covering generation, query construction, indexing, search request shapes, metrics, formulas, and reproduction commands. |
| `../data-generation/corpus-manifest.json` | Corpus-generation manifest and corpus-quality metadata. |
| `../index/index-schema.json` | Azure AI Search index schema used by the full run. |
| `../../data/queries/query-suite.jsonl` | Query specs containing `search_text`, `semantic_intent`, category, filters, and expected IDs. |
| `../../data/labels/relevance-labels.jsonl` | Generator-asserted graded relevance labels. |
| `../../data/generated/source-facts.jsonl` | Structured facts used to generate the synthetic corpus and labels. |
| `../../data/generated/corpus-chunks.jsonl` | Synthetic chunks uploaded to Azure AI Search. |

## Metric notes

For detailed formulas and reproduction commands, read
[`../../docs/methodology.md`](../../docs/methodology.md) alongside
[`whitepaper.md`](whitepaper.md).

- `NDCG@10` is the primary ranking-quality metric; `NDCG@3` is the stricter
  early-rank variant. Both use graded relevance and rank discounting.
- `MRR@10` measures how early the first exact answer-bearing document appears.
- `Recall@50` measures candidate coverage, while `Hit@k` measures whether an
  exact answer-bearing document appears within the top `k`.
- The primary delta is deterministic `semantic_query` NDCG@10 minus the
  identical-control NDCG@10. Bootstrap confidence intervals bound uncertainty
  around that delta, and the Wilcoxon signed-rank p-value is a secondary paired
  shift test.
- Latency is reported as directional mean Search request timing only.

## Raw full-run results

The full ranked output is intentionally not committed directly:

```text
reports\runs\full-suite\results.jsonl
```

That file contains 1,000,200 ranked result records and is about 239 MB locally,
which is too large for normal git history. If raw ranked results are needed for
external review, publish them as a compressed GitHub Release asset and reference
the release from this README.

## Scope notes

- The corpus is synthetic pharmaceutical manufacturing quality/GxP content.
- Labels are generated from structured source facts, not human-adjudicated.
- Category-level findings are exploratory and not multiple-comparison corrected.
- The primary preregistered hypothesis was not supported in this run.
