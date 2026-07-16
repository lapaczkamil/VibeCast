from fastapi import FastAPI

from app.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
