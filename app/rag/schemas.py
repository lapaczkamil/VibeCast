from pydantic import BaseModel


class RagStatusResponse(BaseModel):
    index_ready: bool
    document_count: int
    ollama_reachable: bool
    embed_model: str
    chat_model: str


class RecommendMovieItem(BaseModel):
    tmdb_id: int
    title: str
    year: str | None = None
    poster_url: str | None = None
    reason: str


class RecommendResponse(BaseModel):
    mood_summary: str
    items: list[RecommendMovieItem]
