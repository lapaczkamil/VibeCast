import httpx

from app.spotify.schemas import RecentlyPlayedItem

RECENTLY_PLAYED_URL = "https://api.spotify.com/v1/me/player/recently-played"


def map_recently_played(payload: dict) -> list[RecentlyPlayedItem]:
    items: list[RecentlyPlayedItem] = []
    for entry in payload.get("items", []):
        track = entry.get("track")
        if track is None:
            continue
        items.append(
            RecentlyPlayedItem(
                played_at=entry["played_at"],
                track_id=track["id"],
                name=track["name"],
                artists=[artist["name"] for artist in track.get("artists", [])],
                album=track["album"]["name"],
                spotify_url=track["external_urls"]["spotify"],
            )
        )
    return items


async def fetch_recently_played(access_token: str, limit: int) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(
            RECENTLY_PLAYED_URL,
            params={"limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
        )
