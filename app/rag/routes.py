from fastapi import APIRouter

from app.config import settings
from app.rag.ollama_client import ping_ollama_sync
from app.rag.schemas import RagStatusResponse
from app.rag.store import count_movies

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
