import type { CurrentlyPlayingResponse, SectionState } from "../types";

type NowPlayingDockProps = {
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  onOpenListening: () => void;
};

export function NowPlayingDock({
  currentlyPlaying,
  onOpenListening,
}: NowPlayingDockProps) {
  const track =
    currentlyPlaying.status === "ok"
      ? currentlyPlaying.data?.track ?? null
      : null;
  const isPlaying =
    currentlyPlaying.status === "ok" &&
    currentlyPlaying.data?.is_playing === true;

  return (
    <aside className="now-playing-dock" aria-label="Now playing">
      <button
        type="button"
        className={
          track
            ? "now-playing-dock-card"
            : "now-playing-dock-card now-playing-dock-card--idle"
        }
        onClick={onOpenListening}
      >
        {track ? (
          <>
            {track.image_url ? (
              <img
                src={track.image_url}
                alt=""
                className="now-playing-dock-art"
                width={48}
                height={48}
              />
            ) : (
              <span className="now-playing-dock-art now-playing-dock-art--placeholder" />
            )}
            <span className="now-playing-dock-body">
              <span className="now-playing-dock-label">
                <span
                  className={
                    isPlaying
                      ? "now-playing-dock-live now-playing-dock-live--on"
                      : "now-playing-dock-live"
                  }
                />
                Now playing
              </span>
              <span className="now-playing-dock-title">{track.name}</span>
              <span className="now-playing-dock-meta">
                {track.artists.join(", ")}
              </span>
            </span>
          </>
        ) : (
          <span className="now-playing-dock-body">
            <span className="now-playing-dock-label">Now playing</span>
            <span className="now-playing-dock-title now-playing-dock-title--muted">
              {currentlyPlaying.status === "loading"
                ? "Checking Spotify…"
                : "Nothing playing — open Listening"}
            </span>
          </span>
        )}
      </button>
    </aside>
  );
}
