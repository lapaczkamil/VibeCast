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
    rating: float | None = None
    reason: str
    overview: str = ""


class RecommendResponse(BaseModel):
    mood_summary: str
    items: list[RecommendMovieItem]


class RecommendMoodContextResponse(BaseModel):
    track_line: str
    mood_query: str
    audio_profile: str | None = None
    rerank_enabled: bool = False


class RecommendTrackSeed(BaseModel):
    id: str
    name: str
    artists: list[str]


class RecommendRequest(BaseModel):
    tracks: list[RecommendTrackSeed] = []
