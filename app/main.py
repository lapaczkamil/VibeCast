from fastapi import FastAPI

from app.config import settings
from app.spotify.routes import router as spotify_router

app = FastAPI(title=settings.app_name)
app.include_router(spotify_router)


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
