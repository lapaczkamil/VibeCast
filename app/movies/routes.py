import httpx
from fastapi import APIRouter, HTTPException, Path, Query

from app.config import settings
from app.movies.client import (
    fetch_configuration,
    fetch_movie,
    fetch_movie_search,
    map_movie_detail,
    map_search_results,
    tmdb_configured,
)
from app.movies.schemas import MovieDetailResponse, MovieSearchResponse, MoviesStatus

router = APIRouter()


@router.get("/movies/status", response_model=MoviesStatus)
async def movies_status() -> MoviesStatus:
    if not tmdb_configured(settings.tmdb_api_key):
        return MoviesStatus(configured=False, reachable=False)
    try:
        response = await fetch_configuration(settings.tmdb_api_key)
        reachable = response.status_code == 200
    except httpx.HTTPError:
        reachable = False
    return MoviesStatus(configured=True, reachable=reachable)


@router.get("/movies/search", response_model=MovieSearchResponse)
async def movies_search(
    q: str | None = Query(default=None),
    page: int = Query(default=1),
) -> MovieSearchResponse:
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter q is required")
    if not tmdb_configured(settings.tmdb_api_key):
        raise HTTPException(status_code=503, detail="TMDB API key not configured")
    clamped_page = max(1, page)
    try:
        response = await fetch_movie_search(
            settings.tmdb_api_key, query, clamped_page
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="TMDB API request failed")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="TMDB API request failed")
    return map_search_results(response.json(), query, clamped_page)


@router.get("/movies/{tmdb_id}", response_model=MovieDetailResponse)
async def movie_detail(
    tmdb_id: int = Path(gt=0),
) -> MovieDetailResponse:
    if not tmdb_configured(settings.tmdb_api_key):
        raise HTTPException(status_code=503, detail="TMDB API key not configured")
    try:
        response = await fetch_movie(settings.tmdb_api_key, tmdb_id)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="TMDB API request failed")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Movie not found")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="TMDB API request failed")
    return map_movie_detail(response.json())
