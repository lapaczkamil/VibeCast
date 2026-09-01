from pydantic import BaseModel


class AudioFeatures(BaseModel):
    acousticness: float | None = None
    danceability: float | None = None
    energy: float | None = None
    instrumentalness: float | None = None
    liveness: float | None = None
    speechiness: float | None = None
    valence: float | None = None
    tempo: float | None = None
    loudness: float | None = None
    key: int | None = None
    mode: int | None = None
    id: str | None = None
