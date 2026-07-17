import { setSeedDragData } from "../lib/seedDrag";
import { isSeedSelected } from "../lib/seeds";
import type { CurrentlyPlayingResponse, SeedTrack } from "../types";

type NowPlayingProps = {
  data: CurrentlyPlayingResponse;
  selectedIds?: Set<string> | string[];
  onSeedDragStart?: (track: SeedTrack) => void;
  onSeedDragEnd?: () => void;
};

export function NowPlaying({
  data,
  selectedIds,
  onSeedDragStart,
  onSeedDragEnd,
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
    image_url: track.image_url,
  };
  const draggable = Boolean(onSeedDragStart);
  const selected =
    selectedIds != null && isSeedSelected(selectedIds, track.track_id);

  return (
    <div
      className={
        [
          "now-playing",
          draggable ? "now-playing--draggable" : "",
          selected ? "now-playing--selected" : "",
        ]
          .filter(Boolean)
          .join(" ")
      }
      draggable={draggable}
      onDragStart={
        draggable
          ? (event) => {
              setSeedDragData(event.dataTransfer, seedTrack);
              onSeedDragStart?.(seedTrack);
            }
          : undefined
      }
      onDragEnd={draggable ? () => onSeedDragEnd?.() : undefined}
      title={draggable ? "Drop on the match slot" : undefined}
    >
      {track.image_url && (
        <img
          src={track.image_url}
          alt=""
          className="now-playing-art"
          width={96}
          height={96}
          draggable={false}
        />
      )}
      <div className="now-playing-body">
        <a
          href={track.spotify_url}
          target="_blank"
          rel="noopener noreferrer"
          className="now-playing-title"
          draggable={false}
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
