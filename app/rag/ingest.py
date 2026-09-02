"""CLI: python -m app.rag.ingest"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from typing import Any

import httpx

from app.config import settings
from app.movies.client import (
    _map_rating,
    _map_year,
    fetch_discover_movie_page_sync,
    fetch_genre_list_sync,
    fetch_movie_detail_sync,
    fetch_popular_page_sync,
    map_genre_ids,
)
from app.rag.ollama_client import embed_documents, ping_ollama_sync
from app.rag.store import reset_collection, upsert_movies

BATCH_SIZE = 16
PAGE_SLEEP_SECONDS = 0.25
MAX_PAGE_RETRIES = 4
RETRY_BACKOFF_SECONDS = 1.0
MAX_RETRY_SLEEP_SECONDS = 30.0
# Ingest filters live in Settings; see RAG_MIN_RATING and friends in .env.


MAX_KEYWORDS = 12
# Prefixes of every non-title line, so title stripping cannot eat a real field.
FIELD_PREFIXES = ("Genres:", "Keywords:", "Tagline:", "Overview:")


def embedding_text(document: str) -> str:
    """The text actually embedded, which need not be the stored document.

    The title dominates a document's vector more than any other line, yet says
    almost nothing about mood. Dropping it from the embedding costs nothing:
    the title stays in the document and in the metadata.
    """
    if settings.rag_embed_title:
        return document
    lines = document.splitlines()
    if lines and not lines[0].startswith(FIELD_PREFIXES):
        return "\n".join(lines[1:])
    return document


def _build_document(
    title: str,
    year: str | None,
    genre_names: list[str],
    overview: str,
    keywords: list[str] | None = None,
    tagline: str = "",
) -> str:
    """Overview stays last: overview_from_document() reads to end of text."""
    year_part = f" ({year})" if year else ""
    genres_part = ", ".join(genre_names) if genre_names else "Unknown"
    lines = [f"{title}{year_part}", f"Genres: {genres_part}"]
    if keywords:
        lines.append("Keywords: " + ", ".join(keywords[:MAX_KEYWORDS]))
    if tagline:
        lines.append(f"Tagline: {tagline}")
    lines.append(f"Overview: {overview}")
    return "\n".join(lines)


def parse_enrichment(payload: dict[str, Any]) -> tuple[list[str], str]:
    """Tagline and keyword names from a detail payload, tolerant of gaps."""
    keywords_block = payload.get("keywords") or {}
    raw_keywords = keywords_block.get("keywords") or []
    keywords = [
        str(item.get("name") or "").strip()
        for item in raw_keywords
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    return keywords, str(payload.get("tagline") or "").strip()


def _fetch_enrichment(
    api_key: str,
    movie_ids: list[int],
) -> dict[int, tuple[list[str], str]]:
    """Keywords and taglines for every movie; failures degrade to nothing."""

    def fetch_one(movie_id: int) -> tuple[int, tuple[list[str], str]]:
        try:
            response = fetch_movie_detail_sync(api_key, movie_id)
            if response.status_code != 200:
                return movie_id, ([], "")
            return movie_id, parse_enrichment(response.json())
        except Exception:
            return movie_id, ([], "")

    workers = max(1, settings.rag_enrich_workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(fetch_one, movie_ids))


def _append_from_results(
    results: list[dict[str, Any]],
    *,
    movies: list[dict[str, Any]],
    seen_ids: set[int],
    genre_map: dict[int, str],
    limit: int,
) -> None:
    for result in results:
        if len(movies) >= limit:
            return
        movie_id = result.get("id")
        if movie_id is None or movie_id in seen_ids:
            continue
        overview = (result.get("overview") or "").strip()
        if not overview:
            continue
        rating = _map_rating(result.get("vote_average"))
        # None covers unrated titles: /popular carries no filters of its own,
        # so this is the only gate both sources pass through.
        if rating is None or rating < settings.rag_min_rating:
            continue
        seen_ids.add(movie_id)
        movies.append(
            {
                "tmdb_id": movie_id,
                "title": result.get("title") or "Unknown",
                "year": _map_year(result.get("release_date")),
                "poster_path": result.get("poster_path"),
                "rating": rating,
                "overview": overview,
                "genre_names": map_genre_ids(
                    result.get("genre_ids") or [], genre_map
                ),
            }
        )


def _is_retryable(status_code: int) -> bool:
    """Rate limits and server hiccups are worth another try; 4xx is not."""
    return status_code == 429 or status_code >= 500


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_SLEEP_SECONDS)
        except ValueError:
            pass
    return min(RETRY_BACKOFF_SECONDS * (2**attempt), MAX_RETRY_SLEEP_SECONDS)


def _fetch_page(fetch_page, api_key: str, page: int) -> httpx.Response:
    """Fetch one page, retrying rate limits and server errors with backoff."""
    response = fetch_page(api_key, page)
    for attempt in range(MAX_PAGE_RETRIES):
        if not _is_retryable(response.status_code):
            return response
        delay = _retry_delay(response, attempt)
        print(
            f"  page {page}: HTTP {response.status_code}, retrying in "
            f"{delay:.1f}s ({attempt + 1}/{MAX_PAGE_RETRIES})"
        )
        time.sleep(delay)
        response = fetch_page(api_key, page)
    return response


def _paginate(
    fetch_page,
    api_key: str,
    *,
    movies: list[dict[str, Any]],
    seen_ids: set[int],
    genre_map: dict[int, str],
    limit: int,
) -> str:
    """Collect pages until the limit is hit; returns why it stopped.

    The reason matters: a swallowed 429 and an exhausted source used to look
    identical from the outside, both just yielding a short index.
    """
    page = 1
    while len(movies) < limit:
        response = _fetch_page(fetch_page, api_key, page)
        if response.status_code != 200:
            if movies:
                return f"HTTP {response.status_code} on page {page}"
            raise RuntimeError(
                f"TMDB page {page} failed: HTTP {response.status_code}"
            )
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            return f"page {page} came back empty"
        _append_from_results(
            results,
            movies=movies,
            seen_ids=seen_ids,
            genre_map=genre_map,
            limit=limit,
        )
        total_pages = payload.get("total_pages", page)
        if page >= total_pages:
            return f"source exhausted at page {page}/{total_pages}"
        page += 1
        time.sleep(PAGE_SLEEP_SECONDS)
    return f"quota reached on page {page}"


def _collect_movies(
    api_key: str,
    genre_map: dict[int, str],
    target: int,
) -> list[dict[str, Any]]:
    movies: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    discover_target = min(target, ceil(settings.rag_discover_share * target))

    def discover_fetch(key: str, page: int) -> httpx.Response:
        return fetch_discover_movie_page_sync(
            key,
            page,
            vote_count_gte=settings.rag_discover_vote_count_gte,
            vote_average_gte=settings.rag_min_rating,
        )

    reason = _paginate(
        discover_fetch,
        api_key,
        movies=movies,
        seen_ids=seen_ids,
        genre_map=genre_map,
        limit=discover_target,
    )
    print(f"discover: {len(movies)}/{discover_target} kept, {reason}")

    before_popular = len(movies)
    reason = _paginate(
        fetch_popular_page_sync,
        api_key,
        movies=movies,
        seen_ids=seen_ids,
        genre_map=genre_map,
        limit=target,
    )
    print(
        f"popular: {len(movies) - before_popular} added "
        f"({len(movies)}/{target} total), {reason}"
    )
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

    # The path alone is ambiguous: one Chroma directory holds many collections.
    print(
        f"Ingest -> collection={settings.rag_collection!r} "
        f"path={settings.rag_chroma_path}\n"
        f"  target={settings.rag_movie_target} "
        f"min_rating={settings.rag_min_rating} "
        f"discover_share={settings.rag_discover_share} "
        f"vote_count>={settings.rag_discover_vote_count_gte}\n"
        f"  embed_title={settings.rag_embed_title} "
        f"enrich={settings.rag_enrich_documents} "
        f"embed_model={settings.ollama_embed_model!r}"
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
        raise RuntimeError("No movies collected from TMDB discover/popular pages")

    enrichment: dict[int, tuple[list[str], str]] = {}
    if settings.rag_enrich_documents:
        print(f"Fetching keywords and taglines for {len(movies)} movies...")
        enrichment = _fetch_enrichment(
            api_key, [movie["tmdb_id"] for movie in movies]
        )

    reset_collection()

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
                *enrichment.get(movie["tmdb_id"], ([], "")),
            )
            for movie in batch
        ]
        metadatas = [
            {
                "tmdb_id": movie["tmdb_id"],
                "title": movie["title"],
                "year": movie["year"] or "",
                "poster_path": movie["poster_path"] or "",
                "rating": movie["rating"] if movie["rating"] is not None else 0.0,
            }
            for movie in batch
        ]
        embeddings = embed_documents(
            [embedding_text(document) for document in documents]
        )
        upsert_movies(ids, documents, metadatas, embeddings)
        indexed += len(batch)

    print(
        f"Indexed {indexed} movies into collection "
        f"{settings.rag_collection!r} at {settings.rag_chroma_path}"
    )
    return indexed


def main() -> None:
    try:
        run_ingest()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
