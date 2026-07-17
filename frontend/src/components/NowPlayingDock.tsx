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

  const label = track
    ? `${isPlaying ? "Now playing" : "Paused"}: ${track.name} — ${track.artists.join(", ")}`
    : currentlyPlaying.status === "loading"
      ? "Checking now playing"
      : "Nothing playing";

  return (
    <div className="now-playing-dock" aria-label="Now playing">
      <button
        type="button"
        className={
          track
            ? isPlaying
              ? "now-playing-dock-btn now-playing-dock-btn--live"
              : "now-playing-dock-btn"
            : "now-playing-dock-btn now-playing-dock-btn--idle"
        }
        onClick={onOpenListening}
        title={label}
        aria-label={label}
      >
        {track?.image_url ? (
          <img
            src={track.image_url}
            alt=""
            className="now-playing-dock-art"
            width={22}
            height={22}
          />
        ) : (
          <span
            className={
              track
                ? "now-playing-dock-art now-playing-dock-art--placeholder"
                : "now-playing-dock-art now-playing-dock-art--empty"
            }
            aria-hidden="true"
          />
        )}
        <span className="now-playing-dock-text">
          {track ? (
            track.name
          ) : currentlyPlaying.status === "loading" ? (
            "Checking…"
          ) : (
            "Nothing playing"
          )}
        </span>
        {isPlaying ? (
          <span className="now-playing-dock-pulse" aria-hidden="true" />
        ) : null}
      </button>
    </div>
  );
}
