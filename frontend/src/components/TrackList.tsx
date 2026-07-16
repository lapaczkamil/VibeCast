import type { RecentlyPlayedItem, TopTrackItem } from "../types";

function formatPlayedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function RecentTrackList({ items }: { items: RecentlyPlayedItem[] }) {
  if (items.length === 0) {
    return (
      <p className="empty-state">
        No recent tracks yet. Play something on Spotify and check back.
      </p>
    );
  }

  return (
    <ol className="track-list">
      {items.map((track, index) => (
        <li
          key={`${track.track_id}-${track.played_at}`}
          className="track-item"
          style={{ animationDelay: `${index * 45}ms` }}
        >
          <div className="track-main">
            <a
              href={track.spotify_url}
              target="_blank"
              rel="noopener noreferrer"
              className="track-title"
            >
              {track.name}
            </a>
            <p className="track-meta">
              {track.artists.join(", ")} · {track.album}
            </p>
          </div>
          <time className="track-time" dateTime={track.played_at}>
            {formatPlayedAt(track.played_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}

export function TopTrackList({ items }: { items: TopTrackItem[] }) {
  if (items.length === 0) {
    return (
      <p className="empty-state">
        No top tracks yet. Keep listening and check back later.
      </p>
    );
  }

  return (
    <ol className="track-list">
      {items.map((track, index) => (
        <li
          key={track.track_id}
          className="track-item"
          style={{ animationDelay: `${index * 45}ms` }}
        >
          <span className="track-rank" aria-hidden="true">
            {index + 1}
          </span>
          <div className="track-main">
            <a
              href={track.spotify_url}
              target="_blank"
              rel="noopener noreferrer"
              className="track-title"
            >
              {track.name}
            </a>
            <p className="track-meta">
              {track.artists.join(", ")} · {track.album}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
