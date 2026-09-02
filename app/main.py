from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.movies.routes import router as movies_router
from app.rag.routes import router as rag_router
from app.spotify.routes import router as spotify_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(spotify_router)
app.include_router(movies_router)
app.include_router(rag_router)


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
