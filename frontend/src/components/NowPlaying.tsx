import { isSeedSelected } from "../lib/seeds";
import type { CurrentlyPlayingResponse, SeedTrack } from "../types";

type NowPlayingProps = {
  data: CurrentlyPlayingResponse;
  selectedIds?: Set<string> | string[];
  onToggle?: (track: SeedTrack) => void;
  disabledAdd?: boolean;
};

export function NowPlaying({
  data,
  selectedIds,
  onToggle,
  disabledAdd = false,
}: NowPlayingProps) {
  if (!data.track) {
    return (
      <p className="empty-state">
        Nothing playing right now. Start something on Spotify and refresh.
      </p>
    );
  }

  const track = data.track;
  const seedTrack: SeedTrack = {
    id: track.track_id,
    name: track.name,
    artists: track.artists,
  };
  const selectable = Boolean(onToggle && selectedIds);
  const selected = selectable && isSeedSelected(selectedIds!, track.track_id);

  return (
    <div className="now-playing">
      {selectable ? (
        <button
          type="button"
          className={
            selected ? "seed-toggle seed-toggle--selected" : "seed-toggle"
          }
          aria-pressed={selected}
          aria-label={
            selected
              ? `Remove ${track.name} from seeds`
              : `Add ${track.name} to seeds`
          }
          disabled={disabledAdd && !selected}
          onClick={() => onToggle!(seedTrack)}
        />
      ) : null}
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
          {!data.is_playing ? " · Paused" : ""}
        </p>
      </div>
    </div>
  );
}
