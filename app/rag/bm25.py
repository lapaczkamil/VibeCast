"""Lexical retrieval over the movie documents, complementing the vector search."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi

from app.rag.store import count_movies, get_all_documents

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)

_index: _Bm25Index | None = None


def tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


@dataclass(frozen=True)
class _Bm25Index:
    bm25: BM25Okapi | None
    documents: list[str]
    metadatas: list[dict[str, Any]]

    @property
    def size(self) -> int:
        return len(self.documents)


def _build_index() -> _Bm25Index:
    documents, metadatas = get_all_documents()
    if not documents:
        return _Bm25Index(bm25=None, documents=[], metadatas=[])
    corpus = [tokenize(document) for document in documents]
    return _Bm25Index(bm25=BM25Okapi(corpus), documents=documents, metadatas=metadatas)


def get_index() -> _Bm25Index:
    """Cached index, rebuilt whenever the collection size no longer matches.

    Ingest runs in its own process, so the API cannot be notified directly;
    comparing against the Chroma count is cheap and catches a rebuild.
    """
    global _index
    if _index is None or _index.size != count_movies():
        _index = _build_index()
    return _index


def reset_index() -> None:
    global _index
    _index = None


def search_bm25(
    query: str,
    n_results: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Top lexical matches, ranked. Documents sharing no term are left out."""
    index = get_index()
    tokens = tokenize(query)
    if index.bm25 is None or not tokens or n_results <= 0:
        return [], []

    scores = index.bm25.get_scores(tokens)
    ranked = sorted(
        (position for position in range(index.size) if scores[position] > 0.0),
        key=lambda position: (-scores[position], position),
    )[:n_results]
    return (
        [index.documents[position] for position in ranked],
        [index.metadatas[position] for position in ranked],
    )
