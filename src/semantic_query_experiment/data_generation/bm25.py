from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

from semantic_query_experiment.schemas import CorpusChunk, QuerySpec, RelevanceLabel

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    """Tokenize consistently for corpus difficulty checks."""
    return TOKEN_PATTERN.findall(text.lower())


def bm25_rank(query: str, chunks: Iterable[CorpusChunk]) -> list[tuple[str, float]]:
    """Rank chunks with a small deterministic BM25 implementation."""
    chunk_list = list(chunks)
    tokenized_docs = [
        tokenize(chunk.text) + tokenize(" ".join(chunk.keywords)) for chunk in chunk_list
    ]
    if not chunk_list:
        return []

    doc_freq: Counter[str] = Counter()
    for tokens in tokenized_docs:
        doc_freq.update(set(tokens))

    average_length = sum(len(tokens) for tokens in tokenized_docs) / len(tokenized_docs)
    query_terms = tokenize(query)
    scores: list[tuple[str, float]] = []
    for chunk, tokens in zip(chunk_list, tokenized_docs, strict=True):
        term_counts = Counter(tokens)
        score = 0.0
        doc_length = len(tokens)
        for term in query_terms:
            frequency = term_counts[term]
            if frequency == 0:
                continue
            idf = math.log(1 + (len(chunk_list) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * doc_length / average_length)
            score += idf * (frequency * 2.5) / denominator
        scores.append((chunk.document_id, score))

    return sorted(scores, key=lambda item: (-item[1], item[0]))


def ndcg_at_k(
    ranked_document_ids: list[str],
    relevance_by_document: dict[str, int],
    k: int,
) -> float:
    """Compute NDCG@k for graded labels."""
    dcg = 0.0
    for index, document_id in enumerate(ranked_document_ids[:k], start=1):
        relevance = relevance_by_document.get(document_id, 0)
        dcg += (2**relevance - 1) / math.log2(index + 1)

    ideal_relevances = sorted(relevance_by_document.values(), reverse=True)[:k]
    ideal_dcg = sum(
        (2**relevance - 1) / math.log2(index + 1)
        for index, relevance in enumerate(ideal_relevances, start=1)
    )
    return dcg / ideal_dcg if ideal_dcg else 0.0


def bm25_ndcg_by_category(
    queries: Iterable[QuerySpec],
    chunks: Iterable[CorpusChunk],
    labels: Iterable[RelevanceLabel],
    *,
    k: int = 10,
) -> dict[str, float]:
    """Calculate BM25 NDCG@k grouped by query category."""
    query_list = list(queries)
    chunk_list = list(chunks)
    labels_by_query: dict[str, dict[str, int]] = {}
    for label in labels:
        labels_by_query.setdefault(label.query_id, {})[label.document_id] = label.relevance

    scores_by_category: dict[str, list[float]] = {}
    for query in query_list:
        ranking = bm25_rank(query.search_text, chunk_list)
        ranked_ids = [document_id for document_id, _score in ranking]
        score = ndcg_at_k(ranked_ids, labels_by_query.get(query.query_id, {}), k)
        scores_by_category.setdefault(query.category, []).append(score)

    return {
        category: sum(scores) / len(scores)
        for category, scores in sorted(scores_by_category.items())
        if scores
    }
