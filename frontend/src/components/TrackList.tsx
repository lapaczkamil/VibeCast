import { isSeedSelected } from "../lib/seeds";
import type { RecentlyPlayedItem, SeedTrack, TopTrackItem } from "../types";

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

type SelectableListProps = {
  selectedIds?: Set<string> | string[];
  onToggle?: (track: SeedTrack) => void;
  disabledAdd?: boolean;
};

function SeedToggle({
  track,
  selectedIds,
  onToggle,
  disabledAdd,
}: {
  track: SeedTrack;
  selectedIds: Set<string> | string[];
  onToggle: (track: SeedTrack) => void;
  disabledAdd: boolean;
}) {
  const selected = isSeedSelected(selectedIds, track.id);
  return (
    <button
      type="button"
      className={selected ? "seed-toggle seed-toggle--selected" : "seed-toggle"}
      aria-pressed={selected}
      aria-label={
        selected
          ? `Remove ${track.name} from seeds`
          : `Add ${track.name} to seeds`
      }
      disabled={disabledAdd && !selected}
      onClick={() => onToggle(track)}
    />
  );
}

export function RecentTrackList({
  items,
  selectedIds,
  onToggle,
  disabledAdd = false,
}: { items: RecentlyPlayedItem[] } & SelectableListProps) {
  if (items.length === 0) {
    return (
      <p className="empty-state">
        No recent tracks yet. Play something on Spotify and check back.
      </p>
    );
  }

  const selectable = Boolean(onToggle && selectedIds);

  return (
    <ol className="track-list">
      {items.map((track, index) => {
        const seedTrack: SeedTrack = {
          id: track.track_id,
          name: track.name,
          artists: track.artists,
        };
        return (
          <li
            key={`${track.track_id}-${track.played_at}`}
            className="track-item"
            style={{ animationDelay: `${index * 45}ms` }}
          >
            {selectable ? (
              <SeedToggle
                track={seedTrack}
                selectedIds={selectedIds!}
                onToggle={onToggle!}
                disabledAdd={disabledAdd}
              />
            ) : null}
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
        );
      })}
    </ol>
  );
}

export function TopTrackList({
  items,
  selectedIds,
  onToggle,
  disabledAdd = false,
}: { items: TopTrackItem[] } & SelectableListProps) {
  if (items.length === 0) {
    return (
      <p className="empty-state">
        No top tracks yet. Keep listening and check back later.
      </p>
    );
  }

  const selectable = Boolean(onToggle && selectedIds);

  return (
    <ol className="track-list">
      {items.map((track, index) => {
        const seedTrack: SeedTrack = {
          id: track.track_id,
          name: track.name,
          artists: track.artists,
        };
        return (
          <li
            key={track.track_id}
            className="track-item"
            style={{ animationDelay: `${index * 45}ms` }}
          >
            {selectable ? (
              <SeedToggle
                track={seedTrack}
                selectedIds={selectedIds!}
                onToggle={onToggle!}
                disabledAdd={disabledAdd}
              />
            ) : null}
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
        );
      })}
    </ol>
  );
}
