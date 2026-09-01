"""Rewrites a music mood into a movie-shaped document before embedding it.

The mood query is written in the language of songs and audio features; the
index is written in the language of plot summaries. Embedding a hypothetical
movie instead of the raw mood puts both sides in the same domain.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from app.config import settings
from app.rag.ollama_client import chat_json, embed_query

TMDB_GENRES = (
    "Action, Adventure, Animation, Comedy, Crime, Documentary, Drama, Family, "
    "Fantasy, History, Horror, Music, Mystery, Romance, Science Fiction, "
    "Thriller, War, Western"
)


@dataclass(frozen=True)
class Hypothetical:
    query: str
    mood_summary: str
    generated: bool


def build_hyde_prompt(mood_query: str, lyrics: str | None = None) -> str:
    lyrics_block = (
        f"""
Lyrics excerpt. Use the situation, imagery and point of view it describes.
Do not quote it, and do not write a movie about a song:
{lyrics}
"""
        if lyrics
        else ""
    )
    return f"""You turn a listener's music mood into the description of a movie that matches it.

Music context:
{mood_query}
{lyrics_block}
The audio profile describes the music's emotional register, not the movie's genre.
Read "dark" as somber or melancholic rather than frightening, and treat tempo and
danceability as pacing, not as subject matter.

Invent one movie that fits this mood. Describe it the way a film catalogue would:
tone, pacing, atmosphere, setting, the emotional register. Do not name real
movies, real people or the songs above, and do not write a film about music
unless the mood is genuinely about performing or making music.

Return JSON only with this shape:
{{"mood_summary": "short phrase", "genres": ["..."], "overview": "2 to 3 sentences"}}
Pick genres only from: {TMDB_GENRES}"""


def format_hypothetical_document(genres: list[str], overview: str) -> str:
    """Shape the invented movie like an indexed document."""
    genres_part = ", ".join(genres) if genres else "Unknown"
    return f"Genres: {genres_part}\nOverview: {overview}"


def parse_hyde(raw: str) -> tuple[list[str], str, str]:
    data = json.loads(raw)
    overview = str(data.get("overview") or "").strip()
    if not overview:
        raise ValueError("hypothetical document has no overview")
    genres = [
        str(genre).strip()
        for genre in (data.get("genres") or [])
        if str(genre).strip()
    ]
    return genres, overview, str(data.get("mood_summary") or "").strip()


def hypothetical_document(
    mood_query: str,
    lyrics: str | None = None,
) -> Hypothetical:
    """Never raises: a failed rewrite falls back to embedding the raw mood."""
    if not settings.rag_hyde_enabled:
        return Hypothetical(query=mood_query, mood_summary="", generated=False)
    try:
        genres, overview, mood_summary = parse_hyde(
            chat_json(build_hyde_prompt(mood_query, lyrics))
        )
    except Exception:
        return Hypothetical(query=mood_query, mood_summary="", generated=False)
    return Hypothetical(
        query=format_hypothetical_document(genres, overview),
        mood_summary=mood_summary,
        generated=True,
    )


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def blended_query_embedding(mood_query: str) -> list[float]:
    """Mean of the hypothetical-document and raw-mood embeddings.

    A single generation is noisy; blending keeps one bad hypothetical from
    sinking a query, at the cost of one extra embedding call.
    """
    hypothetical = hypothetical_document(mood_query)
    mood_vector = _normalize(embed_query(mood_query))
    if not hypothetical.generated:
        return mood_vector
    hyde_vector = _normalize(embed_query(hypothetical.query))
    return _normalize(
        [(left + right) / 2.0 for left, right in zip(mood_vector, hyde_vector, strict=True)]
    )
