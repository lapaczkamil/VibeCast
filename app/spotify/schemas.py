from pydantic import BaseModel


class RecentlyPlayedItem(BaseModel):
    played_at: str
    track_id: str
    name: str
    artists: list[str]
    album: str
    spotify_url: str
    image_url: str | None


class RecentlyPlayedResponse(BaseModel):
    items: list[RecentlyPlayedItem]


class SpotifyProfile(BaseModel):
    id: str
    display_name: str
    image_url: str | None
    country: str | None
    product: str | None


class PlayingTrack(BaseModel):
    track_id: str
    name: str
    artists: list[str]
    album: str
    spotify_url: str
    image_url: str | None


class CurrentlyPlayingResponse(BaseModel):
    is_playing: bool
    track: PlayingTrack | None


class TopTrackItem(BaseModel):
    track_id: str
    name: str
    artists: list[str]
    album: str
    spotify_url: str
    image_url: str | None


class TopTracksResponse(BaseModel):
    items: list[TopTrackItem]


class TopArtistItem(BaseModel):
    artist_id: str
    name: str
    genres: list[str]
    image_url: str | None
    spotify_url: str


class TopArtistsResponse(BaseModel):
    items: list[TopArtistItem]


class TrackSearchItem(BaseModel):
    id: str
    name: str
    artists: list[str]
    album: str
    spotify_url: str
    image_url: str | None


class TrackSearchResponse(BaseModel):
    items: list[TrackSearchItem]
