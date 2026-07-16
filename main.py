from fastapi import FastAPI
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
    openai_api_key: str | None = None


settings = Settings()
app = FastAPI(title=settings.app_name)


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
