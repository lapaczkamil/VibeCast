import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_request_lock = asyncio.Lock()
_cache: dict[str, tuple[float, object]] = {}
_last_request_at = 0.0
_blocked_until = 0.0

# Conservative pacing for Development Mode (rolling ~30s window).
MIN_REQUEST_GAP_SECONDS = 4.0
DEFAULT_CIRCUIT_SECONDS = 300.0
_CIRCUIT_FILE = Path("/tmp/vibecast_spotify_circuit")

TTL_ME = 1800.0  # 30 min
TTL_TOP = 1800.0  # 30 min
TTL_RECENT = 180.0  # 3 min — matches frontend steady refresh
TTL_NOW = 3.0  # 3 s — short enough that a track change shows up promptly
TTL_SEARCH = 120.0  # 2 min


def _read_persisted_block() -> float:
    try:
        return float(_CIRCUIT_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0.0


def _write_persisted_block(until: float) -> None:
    try:
        _CIRCUIT_FILE.write_text(str(until))
    except OSError:
        pass


def clear_cache() -> None:
    _cache.clear()


def invalidate_keys(*keys: str) -> None:
    for key in keys:
        _cache.pop(key, None)


def clear_circuit() -> None:
    global _blocked_until
    _blocked_until = 0.0
    try:
        _CIRCUIT_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def is_circuit_open() -> bool:
    global _blocked_until
    persisted = _read_persisted_block()
    if persisted > _blocked_until:
        _blocked_until = persisted
    return time.time() < _blocked_until


def circuit_remaining_seconds() -> float:
    if not is_circuit_open():
        return 0.0
    return max(0.0, _blocked_until - time.time())


def trip_circuit(response: httpx.Response | None = None) -> None:
    global _blocked_until
    delay = DEFAULT_CIRCUIT_SECONDS
    if response is not None:
        raw = response.headers.get("Retry-After")
        if raw:
            try:
                delay = max(delay, min(max(float(raw), 30.0), 600.0))
            except ValueError:
                pass
    _blocked_until = time.time() + delay
    _write_persisted_block(_blocked_until)
    logger.warning(
        "Spotify circuit open — pausing upstream calls for %.0fs",
        delay,
    )


def get_cached(key: str, ttl_seconds: float) -> object | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    cached_at, value = entry
    if time.time() - cached_at >= ttl_seconds:
        return None
    return value


def get_stale(key: str) -> object | None:
    entry = _cache.get(key)
    return entry[1] if entry else None


def set_cached(key: str, value: object) -> None:
    _cache[key] = (time.time(), value)


def cache_age_seconds(key: str) -> float | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    return time.time() - entry[0]


async def _pace_requests() -> None:
    global _last_request_at
    elapsed = time.time() - _last_request_at
    if elapsed < MIN_REQUEST_GAP_SECONDS:
        await asyncio.sleep(MIN_REQUEST_GAP_SECONDS - elapsed)
    _last_request_at = time.time()


async def spotify_request(
    fetch: Callable[[], Awaitable[httpx.Response]],
) -> httpx.Response:
    async with _request_lock:
        if is_circuit_open():
            return httpx.Response(
                429,
                text="Too many requests (circuit open)",
                request=httpx.Request(
                    "GET", "https://api.spotify.com/rate-limited"
                ),
            )
        await _pace_requests()
        response = await fetch()
        if response.status_code == 429:
            logger.warning(
                "Spotify REAL 429 retry_after=%s body=%s",
                response.headers.get("Retry-After"),
                response.text[:300],
            )
            trip_circuit(response)
        return response
