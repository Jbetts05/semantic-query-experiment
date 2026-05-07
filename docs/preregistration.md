# Experiment preregistration

Version: 1.0  
Status: draft until the first data-generation run begins  
Experiment: Azure AI Search `semantic_query` isolation experiment

## Amendment policy

This document is the source of truth for the main experiment. Once data
generation begins, changes must be appended as a new amendment section rather
than edited into the original commitments. The commit SHA that freezes this
version will be recorded in the first run manifest.

## Primary hypothesis

For queries where the L1 retrieval string must include identifiers, jargon,
fielded constraints, or recall-oriented terms, providing a separate
plain-language `semantic_query` for the L2 semantic phase improves final ranking
quality compared with using the L1 retrieval string as the semantic intent.

## Primary contrast and decision rule

Primary contrast:

- Arm A: hybrid retrieval with `semantic_query` set to the byte-identical L1
  retrieval string.
- Arm B: the same hybrid retrieval request with `semantic_query` set to the
  deterministic natural-language intent from the query spec.

Primary metric:

- NDCG@10 using graded relevance labels.

Minimum effect size of interest:

- Mean paired delta NDCG@10 of at least `+0.02` for Arm B over Arm A.

Confirmation rule:

- The paired bootstrap 95% confidence interval for the NDCG@10 delta must be
  entirely above `0.00`, and the point estimate must be at least `+0.02`.

The experiment is still successful if this rule is not met, provided the run
produces a reproducible answer and transparent failure analysis.

## Falsification criteria

The hypothesis is not supported if the deterministic `semantic_query` arm does
not improve NDCG@10 over the identical-control arm, if improvements are
concentrated only in one narrow category, or if observed gains disappear after
excluding lexical-trap cases.

## Fixed experiment scale

- Target indexed chunks: 10,000 to 20,000.
- Target question count: at least 100 questions per category.
- Deployment environment: one experiment environment.
- Query concurrency for quality measurement: 1.

## Corpus

The corpus is synthetic pharmaceutical manufacturing quality and GxP compliance
content generated from structured facts. Document families include SOPs,
deviation investigations, CAPA plans, batch records, audit findings, change
controls, complaint investigations, validation summaries, stability reports, and
data-integrity memos.

The synthetic nature of the corpus limits external validity. Results must be
reported as evidence for this constructed stress test, not as universal
production relevance claims.

## Question categories

Each category contributes at least 100 questions:

1. Exact identifier plus intent: the retrieval query includes identifiers such
   as deviation, SOP, complaint, or batch IDs.
2. Fielded or filtered retrieval: the base query constrains product, site,
   document type, or controlled metadata.
3. Acronym disambiguation: the answer depends on resolving domain acronyms such
   as OOS, OOT, APR/PQR, or CAPA in context.
4. Synonym-only relevance: the best document uses domain equivalents rather
   than the query's surface terms.
5. Lexical trap avoidance: multiple documents share keywords, but only one
   answers the intent.
6. Long compliance question: the user query is a full natural-language question
   containing policy or procedure constraints.
7. Short operational query: the query is brief and search-like.
8. Caption and answer alignment: the best result must contain an extractive
   passage suitable for captions or answers.

## Relevance labels

Labels are graded:

- `3`: exact answer-bearing chunk.
- `2`: same document or directly supporting chunk that materially helps answer
  the query.
- `1`: related context without the answer.
- `0`: irrelevant or lexical trap.

Primary labels come from structured source facts. LLM-assisted judging can be
used only as a secondary quality check. If LLM judging is used, the model,
prompt, temperature, seed where supported, and disagreement-resolution rule must
be recorded in the run manifest.

## Query and semantic intent fields

Each query spec stores:

- `search_text`: the L1 retrieval string.
- `semantic_intent`: the deterministic plain-language intent.
- `expected_document_ids`: graded-relevance source documents/chunks.

The deterministic semantic intent is rendered from structured query facts using
a fixed template per category. It is not rewritten after observing results.
Rendering rules:

1. Use sentence case.
2. Preserve regulated identifiers exactly when they are needed for intent.
3. Remove field syntax, Boolean operators, analyzer hints, and vector keywords.
4. Use the canonical business question template for the category.
5. Collapse repeated whitespace to one ASCII space.
6. Strip leading and trailing whitespace.
7. If rendering produces an empty string, mark the query invalid before the run.

## Experiment arms

All arms must log request JSON, SDK version, service API version, region, model
deployment names, vector settings, semantic configuration, and query rewrite
state.

1. BM25 keyword retrieval.
2. Vector-only retrieval.
3. Hybrid retrieval without semantic ranker.
4. Hybrid plus conventional semantic ranker.
5. Hybrid plus `semantic_query` identical-control:
   - `semantic_query` is byte-identical to `search_text` after the same
     normalization and truncation rules.
6. Hybrid plus deterministic `semantic_query`:
   - `semantic_query` equals the query spec's deterministic `semantic_intent`.
7. Hybrid plus LLM-rewritten `semantic_query`:
   - exploratory only.
   - frozen prompt, temperature `0`, model/version recorded.

The primary analysis uses arms 5 and 6 only.

## Pinned technical settings

Initial pinned settings:

- Azure AI Search API version: `2025-09-01`.
- Python SDK package: `azure-search-documents>=11.6.0,<13.0.0`.
- Semantic configuration name: `gxp-semantic-config`.
- Index name: `semantic-query-gxp`.
- Embedding model target: `text-embedding-3-large`.
- Embedding dimensions: `3072`.
- Query rewrite: disabled for all primary and baseline arms.
- Vector query `k`: `50`.
- Result `top`: `50` for metric capture.
- Chunking: 512 to 1,024 tokens with documented overlap, fixed before indexing.
- Query concurrency for reported quality metrics: `1`.

If quota or policy prevents the target model or API version from being used, an
amendment must be added before data generation begins.

## Metrics

Primary:

- NDCG@10.

Secondary:

- NDCG@3.
- MRR@10.
- Recall@50.
- Top-k expected-document hit rate for k in 1, 3, 5, and 10.
- Answer-bearing passage hit rate.
- Caption relevance.
- Latency p50, p95, and p99.
- Token and request counts for cost estimation.

Dollar costs are not preregistered because prices can change. Token counts,
request counts, service SKU, and deployment capacity are recorded instead.

## Statistical analysis

- Use paired per-query comparisons.
- Use paired bootstrap confidence intervals with a fixed bootstrap seed.
- Use Wilcoxon signed-rank as a secondary view for the primary contrast.
- Treat all non-primary contrasts as exploratory.
- Do not claim per-category significance unless a correction method is
  explicitly added in an amendment before data generation.

## Latency measurement protocol

Latency reporting is secondary and only compared within semantic-enabled arms.

- Warmup requests per arm: 10.
- Measurement requests per query per arm: 1.
- Concurrency: 1.
- Report p50, p95, and p99 by arm.
- Record region, Search SKU, replica/partition count, and timestamp window.

## Analyses intentionally excluded

The main report will not:

- select a different primary metric after seeing results.
- revise semantic intent templates after seeing results.
- headline the exploratory LLM-rewrite arm as the primary result.
- claim broad production superiority from the synthetic corpus alone.
- make uncorrected per-category significance claims.

## Run manifest requirements

Every full run must emit a manifest containing:

- preregistration commit SHA.
- random seeds.
- artifact schema versions.
- Azure region and resource identifiers.
- model names, versions, deployments, and dimensions.
- Search API version and SDK version.
- index schema version.
- semantic configuration name.
- query rewrite state.
- experiment arm definitions.
- generated artifact paths.
