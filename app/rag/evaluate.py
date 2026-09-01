"""CLI: python -m app.rag.evaluate [--variant dense|hybrid|hyde] [-k 8]

Scores retrieval alone, before the LLM selection step, so a change to the
query, the index or the fusion can be judged on its own.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.reccobeats.rerank import genres_from_document

DATASET_PATH = Path("eval/dataset.json")

Ranking = tuple[list[str], list[dict[str, Any]]]
Retriever = Callable[[dict[str, Any], int], Ranking]


@dataclass(frozen=True)
class QueryResult:
    query_id: str
    ranked_ids: list[int]
    relevant: set[int]
    ranked_genres: list[list[str]]
    expected_genres: set[str]
    seconds: float

    @property
    def genre_precision(self) -> float:
        """Share of candidates whose genres overlap the expected neighbourhood.

        Exact-id recall is near-unhittable against a 5000 movie index, so this
        grades what retrieval is really responsible for: landing in the right
        tonal region at all.
        """
        if not self.ranked_genres or not self.expected_genres:
            return 0.0
        folded = {genre.casefold() for genre in self.expected_genres}
        matches = sum(
            1
            for genres in self.ranked_genres
            if any(genre.casefold() in folded for genre in genres)
        )
        return matches / len(self.ranked_genres)

    @property
    def hits(self) -> list[int]:
        return [tmdb_id for tmdb_id in self.ranked_ids if tmdb_id in self.relevant]

    @property
    def recall(self) -> float:
        if not self.relevant:
            return 0.0
        return len(self.hits) / len(self.relevant)

    @property
    def reciprocal_rank(self) -> float:
        for position, tmdb_id in enumerate(self.ranked_ids, start=1):
            if tmdb_id in self.relevant:
                return 1.0 / position
        return 0.0


def load_dataset(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Evaluation dataset not found at {path}")
    return json.loads(path.read_text())["queries"]


def _ranked_ids(metadatas: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    for metadata in metadatas:
        tmdb_id = metadata.get("tmdb_id")
        if tmdb_id is not None:
            ids.append(int(tmdb_id))
    return ids


def score_query(
    query: dict[str, Any],
    retriever: Retriever,
    k: int,
) -> QueryResult:
    started = time.time()
    documents, metadatas = retriever(query, k)
    elapsed = time.time() - started
    return QueryResult(
        query_id=query["id"],
        ranked_ids=_ranked_ids(metadatas)[:k],
        relevant={int(tmdb_id) for tmdb_id in query["relevant"]},
        ranked_genres=[genres_from_document(document) for document in documents[:k]],
        expected_genres=set(query.get("expected_genres") or []),
        seconds=elapsed,
    )


def summarize(results: list[QueryResult]) -> dict[str, float]:
    if not results:
        return {"genre_precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0, "seconds": 0.0}
    count = len(results)
    return {
        "genre_precision": sum(result.genre_precision for result in results) / count,
        "recall": sum(result.recall for result in results) / count,
        "mrr": sum(result.reciprocal_rank for result in results) / count,
        "hit_rate": sum(1.0 for result in results if result.hits) / count,
        "seconds": sum(result.seconds for result in results) / count,
    }


def build_retriever(variant: str) -> Retriever:
    from app.rag.hybrid import hybrid_search
    from app.rag.ollama_client import embed_query
    from app.rag.store import query_movies

    if variant == "dense":
        return lambda query, k: query_movies(embed_query(query["mood"]), k)
    if variant == "hybrid":
        return lambda query, k: hybrid_search(
            query["mood"], embed_query(query["mood"]), k
        )
    if variant == "hyde":
        from app.rag.hyde import hypothetical_document

        def retrieve(query: dict[str, Any], k: int) -> Ranking:
            rewritten = hypothetical_document(query["mood"]).query
            return query_movies(embed_query(rewritten), k)

        return retrieve
    if variant == "hyde_hybrid":
        from app.rag.hyde import hypothetical_document

        def retrieve_hybrid(query: dict[str, Any], k: int) -> Ranking:
            rewritten = hypothetical_document(query["mood"]).query
            return hybrid_search(rewritten, embed_query(rewritten), k)

        return retrieve_hybrid
    if variant == "hyde_lyrics":
        import asyncio

        from app.lyrics.client import fetch_lyrics
        from app.rag.hyde import hypothetical_document

        def retrieve_lyrics(query: dict[str, Any], k: int) -> Ranking:
            lyrics = asyncio.run(
                fetch_lyrics(query.get("track", ""), [query.get("artist", "")])
            )
            rewritten = hypothetical_document(query["mood"], lyrics).query
            return query_movies(embed_query(rewritten), k)

        return retrieve_lyrics
    if variant == "hyde_mood":
        from app.rag.hyde import blended_query_embedding

        return lambda query, k: query_movies(
            blended_query_embedding(query["mood"]), k
        )
    raise RuntimeError(f"Unknown variant: {variant}")


def run(
    variant: str,
    k: int,
    verbose: bool,
    collection: str | None = None,
) -> dict[str, float]:
    from app.config import settings

    if collection:
        settings.rag_collection = collection
    retriever = build_retriever(variant)
    results = [score_query(query, retriever, k) for query in load_dataset()]

    if verbose:
        print(f"{'query':<28} {'genre_p':>8} {'recall':>7} {'rr':>6} {'hits':>6}  {'s':>5}")
        for result in results:
            print(
                f"{result.query_id:<28} {result.genre_precision:>8.2f} "
                f"{result.recall:>7.2f} {result.reciprocal_rank:>6.2f} "
                f"{len(result.hits)}/{len(result.relevant):<4} {result.seconds:>5.1f}"
            )
        print()

    totals = summarize(results)
    print(
        f"variant={variant} collection={settings.rag_collection} "
        f"k={k} n={len(results)}  "
        f"genre_p@{k}={totals['genre_precision']:.3f}  "
        f"recall@{k}={totals['recall']:.3f}  MRR={totals['mrr']:.3f}  "
        f"hit_rate={totals['hit_rate']:.3f}  {totals['seconds']:.1f}s/query"
    )
    return totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="dense", choices=["dense", "hybrid", "hyde", "hyde_mood", "hyde_hybrid", "hyde_lyrics"])
    parser.add_argument("-k", type=int, default=8)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--collection", help="override RAG_COLLECTION for this run")
    args = parser.parse_args()
    try:
        run(args.variant, args.k, verbose=not args.quiet, collection=args.collection)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
