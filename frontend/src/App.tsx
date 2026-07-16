import { useCallback, useEffect, useState } from "react";
import {
  fetchAuthStatus,
  fetchRecentlyPlayed,
  startSpotifyLogin,
} from "./api";
import type { RecentlyPlayedItem } from "./types";

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

function authErrorFromSearch(search: string): boolean {
  return new URLSearchParams(search).get("auth_error") === "1";
}

function TrackList({ items }: { items: RecentlyPlayedItem[] }) {
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

export default function App() {
  const [authError] = useState(() =>
    authErrorFromSearch(window.location.search),
  );
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [tracks, setTracks] = useState<RecentlyPlayedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const status = await fetchAuthStatus();
      setAuthenticated(status.authenticated);

      if (status.authenticated) {
        const data = await fetchRecentlyPlayed();
        setTracks(data.items);
      } else {
        setTracks([]);
      }
    } catch {
      setError("Could not reach VibeCast. Is the backend running?");
      setAuthenticated(null);
      setTracks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authError) {
      const url = new URL(window.location.href);
      url.searchParams.delete("auth_error");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
    void load();
  }, [authError, load]);

  if (loading) {
    return (
      <div className="app">
        <main className="shell shell--center">
          <p className="status-message">Tuning in…</p>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app">
        <main className="shell shell--center">
          <p className="status-message status-message--error">{error}</p>
          <button type="button" className="cta cta--ghost" onClick={load}>
            Try again
          </button>
        </main>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="app">
        <main className="shell shell--landing">
          <h1 className="brand brand--hero">VibeCast</h1>
          <p className="subtitle">
            Movies matched to the mood of your music.
          </p>
          {authError && (
            <p className="auth-error" role="alert">
              Spotify login did not complete. Please try again.
            </p>
          )}
          <button
            type="button"
            className="cta cta--primary"
            onClick={startSpotifyLogin}
          >
            Log in with Spotify
          </button>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="brand brand--header">VibeCast</h1>
        <p className="connected">Connected to Spotify</p>
      </header>
      <main className="shell shell--logged-in">
        <h2 className="section-title">Recently played</h2>
        <TrackList items={tracks} />
      </main>
    </div>
  );
}
