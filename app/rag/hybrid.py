"""Fuses the vector and lexical rankings into a single candidate list."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.rag.bm25 import search_bm25
from app.rag.store import query_movies

Ranking = tuple[list[str], list[dict[str, Any]]]


def reciprocal_rank_fusion(
    rankings: list[Ranking],
    n_results: int,
    k: int | None = None,
) -> Ranking:
    """Combine rankings by position, so incomparable score scales never mix.

    A movie ranked highly by both retrievers outranks one that only a single
    retriever liked, without either score having to be calibrated.
    """
    k = settings.rag_rrf_k if k is None else k
    scores: dict[int, float] = {}
    best_rank: dict[int, int] = {}
    entries: dict[int, tuple[str, dict[str, Any]]] = {}

    for documents, metadatas in rankings:
        for rank, (document, metadata) in enumerate(
            zip(documents, metadatas, strict=True)
        ):
            tmdb_id = metadata.get("tmdb_id")
            if tmdb_id is None:
                continue
            key = int(tmdb_id)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            if key not in best_rank or rank < best_rank[key]:
                best_rank[key] = rank
                entries[key] = (document, metadata)

    ordered = sorted(scores, key=lambda key: (-scores[key], best_rank[key], key))
    selected = ordered[:n_results]
    return (
        [entries[key][0] for key in selected],
        [entries[key][1] for key in selected],
    )


def hybrid_search(
    mood_query: str,
    embedding: list[float],
    n_results: int,
) -> Ranking:
    """The single retrieval entry point; dense-only unless hybrid is enabled."""
    if not settings.rag_hybrid_enabled:
        return query_movies(embedding, n_results)

    candidates = max(n_results, settings.rag_hybrid_candidates)
    dense = query_movies(embedding, candidates)
    lexical = search_bm25(mood_query, candidates)
    return reciprocal_rank_fusion([dense, lexical], n_results)
