from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from semantic_query_experiment.data_generation.bm25 import bm25_ndcg_by_category
from semantic_query_experiment.io import write_jsonl
from semantic_query_experiment.schemas import (
    CorpusChunk,
    CorpusManifest,
    JsonObject,
    QuerySpec,
    RelevanceLabel,
    SourceFact,
)

QUERY_CATEGORIES: tuple[str, ...] = (
    "id_lookup",
    "fielded_filter",
    "acronym_expansion",
    "synonym_swap",
    "lexical_trap",
    "long_compliance",
    "short_operational",
    "caption_answer",
    "temporal_supersession",
)

PRODUCTS = (
    "Asterol API",
    "Vascorin XR",
    "Neuroquel Sterile",
    "Immunavax Fill",
    "Cardioban Granulate",
)
SITES = ("Dublin", "Raleigh", "Singapore", "Uppsala", "Toronto")
DOC_TYPES = (
    "deviation_investigation",
    "capa_plan",
    "batch_record",
    "quality_audit",
    "change_control",
    "stability_trend",
    "validation_summary",
    "data_integrity_memo",
    "sop",
)
ISSUES = (
    ("bioburden excursion", "microbial contamination event", "BIO"),
    ("out-of-trend assay drift", "unexpected potency trend", "OOT"),
    ("ALCOA+ attribution gap", "data integrity authorship issue", "ALCOA"),
    ("clean-in-place conductivity failure", "rinse verification failure", "CIP"),
    ("environmental monitoring alert", "cleanroom microbial alert", "EM"),
    ("hold-time breach", "material storage time excursion", "HTE"),
    ("process validation residual risk", "continued process verification concern", "PV"),
    ("complaint trending signal", "market feedback quality signal", "PQR"),
)
ACTIONS = (
    "shortened the validated hold time and added pre-use bioburden confirmation",
    "introduced a second-person chromatography integration review",
    "retrained operators on aseptic intervention logging with supervisor attestation",
    "replaced the conductivity probe and added pre-batch calibration evidence",
    "segregated the affected lot pending quality-unit disposition",
    "updated the annual product review trigger threshold",
    "requalified the filling-line stopper bowl after intervention mapping",
    "added an effectiveness check using three consecutive conforming batches",
)


@dataclass(frozen=True)
class GeneratedDataset:
    """Generated synthetic artifacts before writing to disk."""

    source_facts: list[SourceFact]
    chunks: list[CorpusChunk]
    queries: list[QuerySpec]
    labels: list[RelevanceLabel]
    manifest: CorpusManifest


@dataclass(frozen=True)
class GenerationPaths:
    """Output paths for generated data artifacts."""

    source_facts_path: Path = Path("data/generated/source-facts.jsonl")
    chunks_path: Path = Path("data/generated/corpus-chunks.jsonl")
    queries_path: Path = Path("data/queries/query-suite.jsonl")
    labels_path: Path = Path("data/labels/relevance-labels.jsonl")
    manifest_path: Path = Path("reports/data-generation/corpus-manifest.json")


def generate_dataset(*, requested_chunk_count: int, seed: int) -> GeneratedDataset:
    """Generate a deterministic GxP corpus with hard negatives and graded labels."""
    if requested_chunk_count < len(QUERY_CATEGORIES) * 3:
        raise ValueError(
            "requested_chunk_count must allow at least one 3-document case per category"
        )

    rng = random.Random(seed)
    case_count = (requested_chunk_count + 2) // 3
    source_facts: list[SourceFact] = []
    chunks: list[CorpusChunk] = []
    queries: list[QuerySpec] = []
    labels: list[RelevanceLabel] = []

    for index in range(case_count):
        category = QUERY_CATEGORIES[index % len(QUERY_CATEGORIES)]
        fact = _build_source_fact(index, rng)
        query = _build_query(index, category, fact)
        gold, sibling_negative, lexical_negative = _build_chunks(fact, query)

        source_facts.append(fact)
        queries.append(query)
        chunks.extend([gold, sibling_negative, lexical_negative])
        labels.extend(_build_labels(query, gold, sibling_negative, lexical_negative))

    manifest = _build_manifest(
        seed=seed,
        requested_chunk_count=requested_chunk_count,
        source_facts=source_facts,
        chunks=chunks,
        queries=queries,
        labels=labels,
    )
    return GeneratedDataset(
        source_facts=source_facts,
        chunks=chunks,
        queries=queries,
        labels=labels,
        manifest=manifest,
    )


def write_generated_dataset(dataset: GeneratedDataset, paths: GenerationPaths) -> None:
    """Write generated artifacts to their standard JSONL/JSON locations."""
    write_jsonl(paths.source_facts_path, dataset.source_facts)
    write_jsonl(paths.chunks_path, dataset.chunks)
    write_jsonl(paths.queries_path, dataset.queries)
    write_jsonl(paths.labels_path, dataset.labels)
    paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text(
        dataset.manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _build_source_fact(index: int, rng: random.Random) -> SourceFact:
    product = PRODUCTS[index % len(PRODUCTS)]
    site = SITES[(index // len(PRODUCTS)) % len(SITES)]
    doc_type = DOC_TYPES[index % len(DOC_TYPES)]
    jargon_term, plain_language_term, acronym = ISSUES[index % len(ISSUES)]
    primary_number = 10000 + index
    secondary_number = 70000 + rng.randrange(9000)
    answer = ACTIONS[(index + rng.randrange(len(ACTIONS))) % len(ACTIONS)]
    return SourceFact(
        fact_id=f"fact-{index:05d}",
        gold_document_id=f"doc-{index:05d}-gold",
        product=product,
        site=site,
        doc_type=doc_type,
        primary_identifier=f"DEV-{primary_number}",
        secondary_identifier=f"BATCH-{secondary_number}",
        jargon_term=jargon_term,
        plain_language_term=plain_language_term,
        answer=answer,
        effective_date=f"2025-{(index % 12) + 1:02d}-{(index % 27) + 1:02d}",
        superseded_identifier=f"{acronym}-REV-{(index % 4) + 1:02d}",
    )


def _build_query(index: int, category: str, fact: SourceFact) -> QuerySpec:
    query_id = f"q-{index:05d}"
    hard_negative_ids = [f"doc-{index:05d}-sibling", f"doc-{index:05d}-lexical-trap"]
    search_text, semantic_intent, filters = _query_text(category, fact)
    return QuerySpec(
        query_id=query_id,
        category=category,
        search_text=search_text,
        semantic_intent=semantic_intent,
        expected_document_ids=[fact.gold_document_id],
        hard_negative_document_ids=hard_negative_ids,
        filters=filters,
    )


def _query_text(category: str, fact: SourceFact) -> tuple[str, str, JsonObject]:
    filters: JsonObject = (
        {"product": fact.product, "site": fact.site} if category == "fielded_filter" else {}
    )
    semantic_intent = (
        f"Which action resolved the {fact.plain_language_term} for {fact.product} at {fact.site}?"
    )
    if category == "id_lookup":
        return (
            f'{fact.primary_identifier} CAPA "{fact.jargon_term}" {fact.product}',
            semantic_intent,
            {},
        )
    if category == "fielded_filter":
        return (
            f'doc_type:{fact.doc_type} product:"{fact.product}" site:"{fact.site}" CAPA outcome',
            semantic_intent,
            filters,
        )
    if category == "acronym_expansion":
        acronym = fact.superseded_identifier.split("-REV-", maxsplit=1)[0]
        return (
            f"{acronym} trend required protocol amendment {fact.product}",
            semantic_intent,
            {},
        )
    if category == "synonym_swap":
        return (
            f"{fact.plain_language_term} remediation quality unit disposition",
            semantic_intent,
            {},
        )
    if category == "lexical_trap":
        return (
            f"{fact.primary_identifier} approved final corrective action {fact.jargon_term}",
            semantic_intent,
            {},
        )
    if category == "long_compliance":
        return (
            "Under GxP expectations, identify the final effectiveness action that "
            f"closed the investigation for {fact.plain_language_term} at {fact.site}.",
            semantic_intent,
            {},
        )
    if category == "short_operational":
        return (f"{fact.product} {fact.jargon_term} fix", semantic_intent, {})
    if category == "caption_answer":
        return (
            f"answer passage for {fact.primary_identifier} effectiveness check",
            semantic_intent,
            {},
        )
    return (
        f"{fact.superseded_identifier} superseded effective {fact.effective_date}",
        f"What currently effective action replaced {fact.superseded_identifier}?",
        {},
    )


def _build_chunks(
    fact: SourceFact,
    query: QuerySpec,
) -> tuple[CorpusChunk, CorpusChunk, CorpusChunk]:
    common_keywords = [
        fact.product,
        fact.site,
        fact.doc_type,
        fact.jargon_term,
        fact.plain_language_term,
        fact.primary_identifier,
        fact.secondary_identifier,
        "corrective action",
        "final CAPA",
        "effectiveness check",
    ]
    gold = CorpusChunk(
        document_id=fact.gold_document_id,
        chunk_id=f"{fact.gold_document_id}-chunk-000",
        title=f"{fact.primary_identifier} final quality-unit disposition",
        doc_type=fact.doc_type,
        product=fact.product,
        site=fact.site,
        batch_id=fact.secondary_identifier,
        deviation_id=fact.primary_identifier,
        sop_id=f"SOP-{1000 + int(fact.fact_id[-5:]) % 8000}",
        keywords=common_keywords,
        text=(
            f"The approved record for {fact.primary_identifier} covers {fact.product} at "
            f"{fact.site}. The investigation confirmed a {fact.jargon_term}, also described "
            f"for operators as a {fact.plain_language_term}. The quality unit approved the "
            f"final CAPA: {fact.answer}. The action became effective on {fact.effective_date} "
            f"and superseded {fact.superseded_identifier}."
        ),
        source_fact_ids=[fact.fact_id],
        expected_answer_spans=[fact.answer],
    )
    sibling_negative = CorpusChunk(
        document_id=query.hard_negative_document_ids[0],
        chunk_id=f"{query.hard_negative_document_ids[0]}-chunk-000",
        title=f"Sibling investigation for {fact.product} at {fact.site}",
        doc_type=fact.doc_type,
        product=fact.product,
        site=fact.site,
        batch_id=f"BATCH-{int(fact.secondary_identifier[-5:]) + 11}",
        deviation_id=f"DEV-{int(fact.primary_identifier[-5:]) + 1}",
        sop_id=None,
        keywords=[
            *common_keywords[:5],
            "sibling investigation",
            "same product",
        ],
        text=(
            f"This sibling record shares {fact.product}, {fact.site}, and {fact.jargon_term} "
            "terminology, but it concerns a different batch and a different root cause. "
            "The quality unit documented background context only; it does not contain the "
            f"final action for {fact.primary_identifier}."
        ),
        source_fact_ids=[fact.fact_id],
        is_hard_negative=True,
        hard_negative_for_query_ids=[query.query_id],
    )
    lexical_negative = CorpusChunk(
        document_id=query.hard_negative_document_ids[1],
        chunk_id=f"{query.hard_negative_document_ids[1]}-chunk-000",
        title=f"Rejected draft action for {fact.primary_identifier}",
        doc_type="draft_capa",
        product=fact.product,
        site=fact.site,
        batch_id=fact.secondary_identifier,
        deviation_id=fact.primary_identifier,
        sop_id=None,
        keywords=[
            fact.primary_identifier,
            fact.jargon_term,
            fact.plain_language_term,
            "corrective action",
            "rejected draft",
            "not final",
        ],
        text=(
            f"A rejected draft for {fact.primary_identifier} used the phrases "
            f"{fact.jargon_term}, {fact.plain_language_term}, corrective action, and "
            "effectiveness check. The draft was explicitly not approved and should not be "
            "used as the final CAPA answer."
        ),
        source_fact_ids=[fact.fact_id],
        is_hard_negative=True,
        hard_negative_for_query_ids=[query.query_id],
    )
    return gold, sibling_negative, lexical_negative


def _build_labels(
    query: QuerySpec,
    gold: CorpusChunk,
    sibling_negative: CorpusChunk,
    lexical_negative: CorpusChunk,
) -> list[RelevanceLabel]:
    return [
        RelevanceLabel(
            query_id=query.query_id,
            document_id=gold.document_id,
            relevance=3,
            rationale="Contains the asserted answer-bearing fact.",
        ),
        RelevanceLabel(
            query_id=query.query_id,
            document_id=sibling_negative.document_id,
            relevance=2,
            rationale="Same product, site, topic, and jargon, but not the answer-bearing fact.",
        ),
        RelevanceLabel(
            query_id=query.query_id,
            document_id=lexical_negative.document_id,
            relevance=1,
            rationale="Shares query terms and identifiers but is an explicitly rejected draft.",
        ),
    ]


def _build_manifest(
    *,
    seed: int,
    requested_chunk_count: int,
    source_facts: list[SourceFact],
    chunks: list[CorpusChunk],
    queries: list[QuerySpec],
    labels: list[RelevanceLabel],
) -> CorpusManifest:
    category_counts = Counter(query.category for query in queries)
    bm25_by_category = bm25_ndcg_by_category(queries, chunks, labels)
    aggregate_bm25 = sum(bm25_by_category.values()) / len(bm25_by_category)
    return CorpusManifest(
        seed=seed,
        requested_chunk_count=requested_chunk_count,
        actual_chunk_count=len(chunks),
        query_count=len(queries),
        source_fact_count=len(source_facts),
        category_counts=dict(sorted(category_counts.items())),
        hard_negative_count=sum(1 for chunk in chunks if chunk.is_hard_negative),
        bm25_ndcg_at_10=round(aggregate_bm25, 6),
        bm25_ndcg_at_10_by_category={
            category: round(score, 6) for category, score in bm25_by_category.items()
        },
        artifact_hashes=_artifact_hashes(source_facts, chunks, queries, labels),
    )


def _artifact_hashes(
    source_facts: list[SourceFact],
    chunks: list[CorpusChunk],
    queries: list[QuerySpec],
    labels: list[RelevanceLabel],
) -> dict[str, str]:
    return {
        "source_facts": _records_hash(source_facts),
        "chunks": _records_hash(chunks),
        "queries": _records_hash(queries),
        "labels": _records_hash(labels),
    }


type HashableRecord = SourceFact | CorpusChunk | QuerySpec | RelevanceLabel


def _records_hash(records: Sequence[HashableRecord]) -> str:
    digest = hashlib.sha256()
    for record in records:
        payload = json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
