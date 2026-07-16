import httpx

from app.movies.schemas import MovieItem, MovieSearchResponse

TMDB_BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w185"
TMDB_TIMEOUT = httpx.Timeout(10.0)


def tmdb_configured(api_key: str | None) -> bool:
    return bool(api_key)


async def fetch_configuration(api_key: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=TMDB_TIMEOUT) as client:
        return await client.get(
            f"{TMDB_BASE_URL}/configuration",
            params={"api_key": api_key},
        )


async def fetch_movie_search(api_key: str, query: str, page: int) -> httpx.Response:
    async with httpx.AsyncClient(timeout=TMDB_TIMEOUT) as client:
        return await client.get(
            f"{TMDB_BASE_URL}/search/movie",
            params={"api_key": api_key, "query": query, "page": page},
        )


def _map_year(release_date: str | None) -> str | None:
    if release_date and len(release_date) >= 4:
        return release_date[:4]
    return None


def _map_poster_url(poster_path: str | None) -> str | None:
    if poster_path:
        return f"{POSTER_BASE_URL}{poster_path}"
    return None


def map_search_results(payload: dict, query: str, page: int) -> MovieSearchResponse:
    items: list[MovieItem] = []
    for result in payload.get("results", []):
        items.append(
            MovieItem(
                id=result["id"],
                title=result["title"],
                year=_map_year(result.get("release_date")),
                overview=result.get("overview") or "",
                poster_url=_map_poster_url(result.get("poster_path")),
            )
        )
    return MovieSearchResponse(
        query=query,
        page=page,
        total_results=payload.get("total_results", 0),
        items=items,
    )
