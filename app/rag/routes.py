from fastapi import APIRouter, HTTPException

from app.config import settings
from app.rag.ollama_client import ping_ollama_sync
from app.rag.recommend import RecommendationParseError, recommend_for_user
from app.rag.schemas import RagStatusResponse, RecommendRequest, RecommendResponse
from app.rag.store import count_movies
from app.spotify import oauth

router = APIRouter()


@router.get("/rag/status", response_model=RagStatusResponse)
def rag_status() -> RagStatusResponse:
    document_count = count_movies()
    return RagStatusResponse(
        index_ready=document_count > 0,
        document_count=document_count,
        ollama_reachable=ping_ollama_sync(),
        embed_model=settings.ollama_embed_model,
        chat_model=settings.ollama_chat_model,
    )


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(body: RecommendRequest = RecommendRequest()) -> RecommendResponse:
    if oauth.get_tokens() is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if count_movies() == 0:
        raise HTTPException(
            status_code=503,
            detail="Movie index not built; run ingest",
        )

    if not ping_ollama_sync():
        raise HTTPException(status_code=503, detail="Ollama unreachable")

    try:
        return await recommend_for_user(body)
    except RecommendationParseError:
        raise HTTPException(
            status_code=502,
            detail="Failed to parse recommendation response",
        ) from None
