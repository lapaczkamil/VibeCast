import httpx

from app.config import settings

OLLAMA_TIMEOUT = httpx.Timeout(30.0)

QWEN3_QUERY_TASK = (
    "Given a music listening mood, retrieve movies that match the atmosphere and tone"
)


def _uses_nomic_prefixes(model: str) -> bool:
    return "nomic-embed" in model.lower()


def _uses_qwen3_prefixes(model: str) -> bool:
    return "qwen3-embedding" in model.lower()


def prepare_document_text(text: str, *, model: str | None = None) -> str:
    model = model or settings.ollama_embed_model
    if _uses_nomic_prefixes(model):
        return f"search_document: {text}"
    return text


def prepare_query_text(text: str, *, model: str | None = None) -> str:
    model = model or settings.ollama_embed_model
    if _uses_nomic_prefixes(model):
        return f"search_query: {text}"
    if _uses_qwen3_prefixes(model):
        return f"Instruct: {QWEN3_QUERY_TASK}\nQuery:{text}"
    return text


def _embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        for text in texts:
            response = client.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={"model": settings.ollama_embed_model, "prompt": text},
            )
            response.raise_for_status()
            payload = response.json()
            embeddings.append(payload["embedding"])
    return embeddings


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed_texts([prepare_document_text(text) for text in texts])


def embed_query(text: str) -> list[float]:
    return _embed_texts([prepare_query_text(text)])[0]


def chat_json(prompt: str) -> str:
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload["message"]["content"]


async def ping_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def ping_ollama_sync() -> bool:
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            response = client.get(f"{settings.ollama_base_url}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False
