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


class MovieSearchResponse(BaseModel):
    query: str
    page: int
    total_results: int
    items: list[MovieItem]
