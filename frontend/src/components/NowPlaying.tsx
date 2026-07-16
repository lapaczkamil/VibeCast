import type { CurrentlyPlayingResponse } from "../types";

type NowPlayingProps = {
  data: CurrentlyPlayingResponse;
};

export function NowPlaying({ data }: NowPlayingProps) {
  if (!data.is_playing || !data.track) {
    return (
      <p className="empty-state">
        Nothing playing right now. Start something on Spotify and refresh.
      </p>
    );
  }

  const track = data.track;

  return (
    <div className="now-playing">
      {track.image_url && (
        <img
          src={track.image_url}
          alt=""
          className="now-playing-art"
          width={96}
          height={96}
        />
      )}
      <div className="now-playing-body">
        <a
          href={track.spotify_url}
          target="_blank"
          rel="noopener noreferrer"
          className="now-playing-title"
        >
          {track.name}
        </a>
        <p className="now-playing-meta">
          {track.artists.join(", ")} · {track.album}
        </p>
      </div>
    </div>
  );
}
