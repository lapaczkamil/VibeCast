from pydantic import BaseModel


class RecentlyPlayedItem(BaseModel):
    played_at: str
    track_id: str
    name: str
    artists: list[str]
    album: str
    spotify_url: str


class RecentlyPlayedResponse(BaseModel):
    items: list[RecentlyPlayedItem]
