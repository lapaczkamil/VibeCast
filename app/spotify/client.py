import httpx

from app.spotify.schemas import (
    CurrentlyPlayingResponse,
    PlayingTrack,
    RecentlyPlayedItem,
    SpotifyProfile,
    TopArtistItem,
    TopTrackItem,
)

RECENTLY_PLAYED_URL = "https://api.spotify.com/v1/me/player/recently-played"
ME_URL = "https://api.spotify.com/v1/me"
CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
TOP_TRACKS_URL = "https://api.spotify.com/v1/me/top/tracks"
TOP_ARTISTS_URL = "https://api.spotify.com/v1/me/top/artists"


def _first_image_url(images: list[dict] | None) -> str | None:
    if not images:
        return None
    return images[0].get("url")


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


def map_me(payload: dict) -> SpotifyProfile:
    return SpotifyProfile(
        id=payload["id"],
        display_name=payload.get("display_name") or payload["id"],
        image_url=_first_image_url(payload.get("images")),
        country=payload.get("country"),
        product=payload.get("product"),
    )


def map_currently_playing(payload: dict) -> CurrentlyPlayingResponse:
    item = payload.get("item")
    if item is None:
        return CurrentlyPlayingResponse(is_playing=False, track=None)
    return CurrentlyPlayingResponse(
        is_playing=bool(payload.get("is_playing")),
        track=PlayingTrack(
            track_id=item["id"],
            name=item["name"],
            artists=[artist["name"] for artist in item.get("artists", [])],
            album=item["album"]["name"],
            spotify_url=item["external_urls"]["spotify"],
            image_url=_first_image_url(item.get("album", {}).get("images")),
        ),
    )


def map_top_tracks(payload: dict) -> list[TopTrackItem]:
    items: list[TopTrackItem] = []
    for track in payload.get("items", []):
        items.append(
            TopTrackItem(
                track_id=track["id"],
                name=track["name"],
                artists=[artist["name"] for artist in track.get("artists", [])],
                album=track["album"]["name"],
                spotify_url=track["external_urls"]["spotify"],
            )
        )
    return items


def map_top_artists(payload: dict) -> list[TopArtistItem]:
    items: list[TopArtistItem] = []
    for artist in payload.get("items", []):
        items.append(
            TopArtistItem(
                artist_id=artist["id"],
                name=artist["name"],
                genres=artist.get("genres", []),
                image_url=_first_image_url(artist.get("images")),
                spotify_url=artist["external_urls"]["spotify"],
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


async def fetch_me(access_token: str) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(
            ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )


async def fetch_currently_playing(access_token: str) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(
            CURRENTLY_PLAYING_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )


async def fetch_top_tracks(
    access_token: str, limit: int, time_range: str
) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(
            TOP_TRACKS_URL,
            params={"limit": limit, "time_range": time_range},
            headers={"Authorization": f"Bearer {access_token}"},
        )


async def fetch_top_artists(
    access_token: str, limit: int, time_range: str
) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(
            TOP_ARTISTS_URL,
            params={"limit": limit, "time_range": time_range},
            headers={"Authorization": f"Bearer {access_token}"},
        )
