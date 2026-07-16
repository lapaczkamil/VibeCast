from pydantic import BaseModel


class RagStatusResponse(BaseModel):
    index_ready: bool
    document_count: int
    ollama_reachable: bool
    embed_model: str
    chat_model: str
