from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VibeCast"
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://127.0.0.1:8000/callback"
    frontend_url: str = "http://127.0.0.1:5173"
    openai_api_key: str | None = None
    tmdb_api_key: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    rag_collection: str = "movies"
    rag_movie_target: int = 10000
    rag_chroma_path: str = "data/chroma"
    rag_min_rating: float = 7.0
    rag_discover_share: float = 0.6
    rag_discover_vote_count_gte: int = 500
    rag_hyde_enabled: bool = True
    rag_enrich_documents: bool = True
    rag_enrich_workers: int = 8
    rag_hybrid_enabled: bool = False
    rag_hybrid_candidates: int = 32
    rag_rrf_k: int = 60
    reccobeats_base_url: str = "https://api.reccobeats.com"
    reccobeats_timeout_seconds: float = 4.0
    lyrics_enabled: bool = True
    lrclib_base_url: str = "https://lrclib.net"
    lyrics_timeout_seconds: float = 4.0
    lyrics_max_chars: int = 1200


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
