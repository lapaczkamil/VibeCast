import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.reccobeats.schemas import AudioFeatures

logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 3600.0
_cache: dict[str, tuple[float, AudioFeatures]] = {}


def clear_audio_features_cache() -> None:
    _cache.clear()


def _parse_features(payload: dict[str, Any]) -> AudioFeatures | None:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        return None
    item = content[0]
    if not isinstance(item, dict):
        return None
    return AudioFeatures.model_validate(item)


async def fetch_audio_features(spotify_track_id: str) -> AudioFeatures | None:
    track_id = (spotify_track_id or "").strip()
    if not track_id:
        return None
    cached = _cache.get(track_id)
    if cached and cached[0] > time.time():
        return cached[1]
    url = f"{settings.reccobeats_base_url.rstrip('/')}/v1/audio-features"
    try:
        async with httpx.AsyncClient(
            timeout=settings.reccobeats_timeout_seconds
        ) as http:
            response = await http.get(
                url,
                params={"ids": track_id},
                headers={"Accept": "application/json"},
            )
        if response.status_code != 200:
            logger.warning(
                "ReccoBeats audio-features failed track=%s status=%s",
                track_id,
                response.status_code,
            )
            return None
        features = _parse_features(response.json())
        if features is None:
            return None
        _cache[track_id] = (time.time() + _CACHE_TTL_SECONDS, features)
        return features
    except Exception as exc:
        logger.warning(
            "ReccoBeats audio-features error track=%s err=%s",
            track_id,
            exc,
        )
        return None
