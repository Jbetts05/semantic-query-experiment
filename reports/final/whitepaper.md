# Evaluating Azure AI Search `semantic_query` in Hybrid Retrieval

## Executive summary

This whitepaper summarizes a controlled experiment comparing Azure AI Search retrieval strategies, with particular focus on the `semantic_query` request parameter. The goal was not to produce a marketing benchmark or a universal claim. It was to isolate one design question for professional search and RAG systems: **when base retrieval text and semantic-ranking intent are allowed to differ, does ranking quality improve?**

The strongest aggregate result across the tested arms was **hybrid retrieval with semantic ranking using the same query text for both retrieval and semantic ranking**. Both `hybrid_semantic` and the byte-identical `hybrid_semantic_query_control` arm achieved **NDCG@10 = 0.3698**. The separate rule-based `semantic_query` arm achieved **NDCG@10 = 0.3461**, for a paired primary delta of **-0.0237** NDCG@10 versus control. A paired bootstrap over query-level deltas produced a 95% CI of **[-0.0340, -0.0133]**, recorded in `reports\final\statistical-summary.json`.

Per the predefined decision rule in `docs\preregistration.md`, the primary hypothesis was **not supported**: the rule-based `semantic_query` arm did not improve NDCG@10 by at least +0.02 over the identical-control arm, and its paired confidence interval was entirely below zero. The practical finding is still nuanced. A separate `semantic_query` helped several categories, especially fielded/filter-style retrieval and long compliance questions, while hurting identifier lookup and temporal supersession queries. The aggregate result is therefore not a general rejection of `semantic_query`; it shows that separate semantic intent should be **targeted and validated by query category**, not enabled globally without measurement.

## Experimental setup

The experiment used a synthetic pharmaceutical manufacturing quality and GxP compliance corpus. This domain was selected because it stresses search systems with exact identifiers, controlled terminology, abbreviations, synonyms, and compliance-oriented answer passages. Examples include CAPA, OOS, OOT, APR/PQR, ALCOA+, deviations, change controls, validation records, stability reports, SOPs, batch IDs, deviation IDs, and revision identifiers.

The run indexed **10,002** chunks into Azure AI Search and evaluated **3,334** queries across **six** arms, producing **1,000,200** ranked result records. Query categories were intentionally balanced: 371 each for acronym expansion, fielded filter, identifier lookup, and synonym swap; 370 each for caption/answer alignment, lexical trap, long compliance, short operational, and temporal supersession. Relevance labels were generator-asserted from structured source facts using graded relevance: exact answer-bearing chunk, supporting chunk, related context, or hard negative.

The primary comparison was defined before the full run in `docs\preregistration.md`: compare hybrid retrieval with `semantic_query` set to the byte-identical retrieval string against the same hybrid request with `semantic_query` set to a rule-based natural-language intent. The preregistration file was created in commit `fbfda1673e8a72e56ced615b5427428c30ca58b1`; the last committed change touching it before data generation was `6d6e179bf9c02e35d88727a1a398c644fc6b4b47`. Query rewrite was disabled to keep the comparison focused on the request parameter itself.

| Configuration | Value |
| --- | --- |
| Azure region | `swedencentral` |
| Azure AI Search service | `semqry-search-556dc8sc` |
| Search API version | `2025-09-01` |
| Search SKU | `basic` |
| Index | `semantic-query-gxp-8fcc73ca-azure-openai-text-embedding-3-large-text-embedding-3-large-2024-10-21-3072` |
| Semantic configuration | `gxp-semantic-config` |
| Text analyzer | `en.microsoft` |
| Identifier analyzer | `keyword` |
| Embedding model | `text-embedding-3-large`, 3,072 dimensions |
| Vector profile | HNSW cosine, `m=4`, `efConstruction=400`, `efSearch=500` |
| Vector `k` / result `top` | `50` / `50` |
| Query rewrite | Disabled for all primary and baseline arms |

## What changed between retrieval query and `semantic_query`

The independent variable was a deterministic, rule-based semantic intent, not an LLM rewrite. Each query spec stored both `search_text` and `semantic_intent`. The renderer removed field syntax, Boolean/search-like phrasing, and some recall-oriented terms, then emitted a plain-language business question. It also attempted to preserve regulated identifiers when needed, but the results show that this rule was not sufficient for identifier and temporal cases.

Representative examples:

| Category | Retrieval query (`search_text`) | Separate `semantic_query` |
| --- | --- | --- |
| Identifier lookup | `DEV-10000 CAPA "bioburden excursion" Asterol API` | `Which action resolved the microbial contamination event for Asterol API at Dublin?` |
| Fielded filter | `doc_type:capa_plan product:"Vascorin XR" site:"Dublin" CAPA outcome` | `Which action resolved the unexpected potency trend for Vascorin XR at Dublin?` |
| Long compliance | `Under GxP expectations, identify the final effectiveness action that closed the investigation for material storage time excursion at Raleigh.` | `Which action resolved the material storage time excursion for Asterol API at Raleigh?` |
| Synonym swap | `rinse verification failure remediation quality unit disposition` | `Which action resolved the rinse verification failure for Immunavax Fill at Dublin?` |
| Temporal supersession | `BIO-REV-01 superseded effective 2025-09-09` | `What currently effective action replaced BIO-REV-01?` |

These examples explain the main result pattern. In fielded and long-form queries, the semantic intent often clarified the actual question. In identifier-heavy cases, the semantic query could soften or remove discriminating lexical evidence that the semantic ranker still used effectively.

## Results

The aggregate metrics show that semantic ranking was valuable in this corpus, while the vector-only arm was weak and hybrid without semantic ranking underperformed BM25 on ranking quality. That hybrid-vs-BM25 inversion is an important caveat: the vector representation and fusion settings were not independently tuned for maximum retrieval quality. The controlled comparison remains useful because the primary arms used the same retrieval setup and differed only in semantic-ranking query text.

| Arm | NDCG@10 | NDCG@3 | MRR@10 | Recall@50 | Hit@1 | Hit@5 | Hit@10 | Mean latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid_semantic` | **0.3698** | **0.3397** | **0.3822** | 0.4505 | **0.3503** | 0.4169 | 0.4931 | 582.8 |
| `hybrid_semantic_query_control` | **0.3698** | **0.3397** | **0.3822** | 0.4505 | **0.3503** | 0.4169 | 0.4931 | 582.6 |
| `hybrid_semantic_query_deterministic` | 0.3461 | 0.2802 | 0.3383 | 0.4505 | 0.2564 | **0.4472** | **0.5504** | 582.9 |
| `bm25` | 0.2823 | 0.2585 | 0.2196 | 0.4384 | 0.0612 | 0.3809 | 0.4223 | 244.3 |
| `hybrid` | 0.1657 | 0.1229 | 0.1764 | 0.4505 | 0.1419 | 0.1998 | 0.3221 | 549.1 |
| `vector` | 0.0495 | 0.0279 | 0.0461 | 0.1529 | 0.0198 | 0.0762 | 0.1314 | 321.0 |

Recall@50 parity across the hybrid semantic arms is expected by design because `semantic_query` changes the semantic ranking stage, not the L1 candidate retrieval request. The ranking difference appears after candidate generation: the separate semantic query lowered aggregate NDCG@10 and reduced Hit@1 from **0.3503** to **0.2564**, even though it improved deeper Hit@5 and Hit@10. In this run, the separate semantic intent was more likely to include the expected document somewhere in the top 10, but less likely to place it first.

The category table below is exploratory. It reports uncorrected point estimates by category; no multiple-comparison correction or per-category significance claim is made.

| Category | n | Control NDCG@10 | Rule-based `semantic_query` NDCG@10 | Delta |
| --- | ---: | ---: | ---: | ---: |
| Fielded/filter-style retrieval | 371 | 0.2018 | 0.4678 | **+0.2660** |
| Long compliance questions | 370 | 0.0685 | 0.2611 | **+0.1925** |
| Short operational queries | 370 | 0.0051 | 0.1040 | **+0.0988** |
| Synonym swaps | 371 | 0.0046 | 0.0859 | **+0.0813** |
| Acronym expansion | 371 | 0.0019 | 0.0545 | **+0.0526** |
| Caption/answer alignment | 370 | 0.8944 | 0.8830 | **-0.0114** |
| Lexical trap avoidance | 370 | 0.9597 | 0.8726 | **-0.0871** |
| Temporal supersession | 370 | 0.2185 | 0.0130 | **-0.2055** |
| Identifier lookup | 371 | 0.9746 | 0.3742 | **-0.6003** |

Across all queries, 28.6% had a positive per-query NDCG@10 delta, 28.0% had a negative delta, and 43.4% were unchanged. The aggregate negative result was driven primarily by large losses in identifier lookup and temporal supersession.

## Interpretation

The experiment supports three practical conclusions.

First, **hybrid retrieval plus semantic ranking is the strongest default baseline in this experiment**. It substantially outperformed BM25, vector-only, and non-semantic hybrid ranking on aggregate NDCG@10, MRR@10, and Hit@1.

Second, **the preregistered primary hypothesis was not supported, but separate `semantic_query` appears category-sensitive in exploratory analysis**. It helped when the retrieval query was search-like, fielded, terse, synonym-heavy, or compliance-worded. In these cases, a plain-language semantic intent gave the reranker a clearer question than the operational retrieval string.

Third, **separate `semantic_query` can hurt when exact tokens carry the answer identity**. Identifier lookup and temporal supersession queries depended heavily on IDs, effective dates, revision markers, or exact controlled terms. The rule-based semantic query sometimes made those queries more readable while making them less discriminative.

## Limitations and recommended next steps

This is a reproducible synthetic stress test, not a production benchmark. The corpus and labels were generated from structured facts, which makes the experiment auditable but also introduces circularity risk: the same synthetic design choices shape the documents, relevance labels, hard negatives, and query templates. A production decision should repeat the comparison on representative business content with human-reviewed relevance judgments.

The vector-only and non-semantic hybrid baselines were weak in this run, especially vector-only Recall@50 at **0.1529** despite a 3,072-dimension `text-embedding-3-large` index. That is low enough that future work should treat vector configuration, query embedding strategy, and fusion weighting as open engineering questions rather than assuming this run represents an optimized vector baseline. Latency is reported as a mean only in this whitepaper; p50/p95/p99 latency should be added before operational capacity planning.

The recommended next step is not to discard `semantic_query`, but to use it selectively. A production implementation should preserve identifiers and temporal constraints in semantic intent, gate the feature by query category, and evaluate an LLM-rewritten semantic-query arm separately from the rule-based template tested here. The result is useful precisely because it is mixed: it identifies where separate semantic intent can help, where it can hurt, and why professionals should validate the behavior rather than enabling it as a global default.

## Artifact references

- Whitepaper: `reports\final\whitepaper.md`
- Final report: `reports\final\report.md`
- Metrics: `reports\final\metrics.json`
- Statistical summary: `reports\final\statistical-summary.json`
- Chart: `reports\final\ndcg-at-10.svg`
- Raw ranked results: `reports\runs\full-suite\results.jsonl`
- Preregistration: `docs\preregistration.md`
