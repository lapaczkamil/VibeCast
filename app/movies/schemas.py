from pydantic import BaseModel


class MoviesStatus(BaseModel):
    configured: bool
    reachable: bool


class MovieItem(BaseModel):
    id: int
    title: str
    year: str | None
    overview: str
    poster_url: str | None
    rating: float | None = None


class MovieSearchResponse(BaseModel):
    query: str
    page: int
    total_results: int
    items: list[MovieItem]


class MovieDetailResponse(BaseModel):
    tmdb_id: int
    title: str
    year: str | None
    overview: str
    tagline: str
    genres: list[str]
    runtime: int | None
    poster_url: str | None
