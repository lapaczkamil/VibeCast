"""CLI: python -m app.rag.ingest"""

from __future__ import annotations

import sys
import time
from typing import Any

from app.config import settings
from app.movies.client import (
    _map_year,
    fetch_genre_list_sync,
    fetch_popular_page_sync,
    map_genre_ids,
)
from app.rag.ollama_client import embed_texts, ping_ollama_sync
from app.rag.store import upsert_movies

BATCH_SIZE = 16
PAGE_SLEEP_SECONDS = 0.25


def _build_document(
    title: str,
    year: str | None,
    genre_names: list[str],
    overview: str,
) -> str:
    year_part = f" ({year})" if year else ""
    genres_part = ", ".join(genre_names) if genre_names else "Unknown"
    return f"{title}{year_part}\nGenres: {genres_part}\nOverview: {overview}"


def _collect_movies(
    api_key: str,
    genre_map: dict[int, str],
    target: int,
) -> list[dict[str, Any]]:
    movies: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    page = 1

    while len(movies) < target:
        response = fetch_popular_page_sync(api_key, page)
        if response.status_code != 200:
            raise RuntimeError(
                f"TMDB popular page {page} failed: HTTP {response.status_code}"
            )
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            break

        for result in results:
            movie_id = result.get("id")
            if movie_id is None or movie_id in seen_ids:
                continue
            overview = (result.get("overview") or "").strip()
            if not overview:
                continue
            seen_ids.add(movie_id)
            movies.append(
                {
                    "tmdb_id": movie_id,
                    "title": result.get("title") or "Unknown",
                    "year": _map_year(result.get("release_date")),
                    "poster_path": result.get("poster_path"),
                    "overview": overview,
                    "genre_names": map_genre_ids(
                        result.get("genre_ids") or [], genre_map
                    ),
                }
            )
            if len(movies) >= target:
                break

        if page >= payload.get("total_pages", page):
            break
        page += 1
        time.sleep(PAGE_SLEEP_SECONDS)

    return movies


def run_ingest() -> int:
    api_key = settings.tmdb_api_key
    if not api_key:
        raise RuntimeError("TMDB_API_KEY is required for ingest")

    if not ping_ollama_sync():
        raise RuntimeError(
            f"Ollama is not reachable at {settings.ollama_base_url}; "
            "start Ollama and pull the embed model"
        )

    genre_response = fetch_genre_list_sync(api_key)
    if genre_response.status_code != 200:
        raise RuntimeError("Failed to fetch TMDB genre list")
    genre_map = {
        genre["id"]: genre["name"]
        for genre in genre_response.json().get("genres", [])
    }

    movies = _collect_movies(api_key, genre_map, settings.rag_movie_target)
    if not movies:
        raise RuntimeError("No movies collected from TMDB popular pages")

    indexed = 0
    for start in range(0, len(movies), BATCH_SIZE):
        batch = movies[start : start + BATCH_SIZE]
        ids = [str(movie["tmdb_id"]) for movie in batch]
        documents = [
            _build_document(
                movie["title"],
                movie["year"],
                movie["genre_names"],
                movie["overview"],
            )
            for movie in batch
        ]
        metadatas = [
            {
                "tmdb_id": movie["tmdb_id"],
                "title": movie["title"],
                "year": movie["year"] or "",
                "poster_path": movie["poster_path"] or "",
            }
            for movie in batch
        ]
        embeddings = embed_texts(documents)
        upsert_movies(ids, documents, metadatas, embeddings)
        indexed += len(batch)

    print(f"Indexed {indexed} movies into {settings.rag_chroma_path}")
    return indexed


def main() -> None:
    try:
        run_ingest()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
