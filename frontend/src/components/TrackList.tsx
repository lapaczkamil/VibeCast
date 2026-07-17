import { useState } from "react";
import { setSeedDragData } from "../lib/seedDrag";
import { isSeedSelected } from "../lib/seeds";
import type { RecentlyPlayedItem, SeedTrack, TopTrackItem } from "../types";

const LIST_PREVIEW = 10;

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
  onSeedDragStart?: (track: SeedTrack) => void;
  onSeedDragEnd?: () => void;
};

function TrackArt({
  imageUrl,
  label,
}: {
  imageUrl: string | null | undefined;
  label: string;
}) {
  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt=""
        className="track-art"
        width={40}
        height={40}
        loading="lazy"
        draggable={false}
      />
    );
  }
  return (
    <span className="track-art track-art--placeholder" aria-hidden="true">
      {label.slice(0, 1).toUpperCase()}
    </span>
  );
}

function trackItemClass(
  selected: boolean,
  draggable: boolean,
): string {
  return [
    "track-item",
    draggable ? "track-item--draggable" : "",
    selected ? "track-item--selected" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function ListExpandToggle({
  total,
  expanded,
  onToggle,
}: {
  total: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  if (total <= LIST_PREVIEW) return null;
  return (
    <button
      type="button"
      className="track-list-expand"
      onClick={onToggle}
      aria-expanded={expanded}
    >
      {expanded ? "Show less" : `Show more (${total - LIST_PREVIEW} more)`}
    </button>
  );
}

export function RecentTrackList({
  items,
  selectedIds,
  onSeedDragStart,
  onSeedDragEnd,
}: { items: RecentlyPlayedItem[] } & SelectableListProps) {
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) {
    return (
      <p className="empty-state">
        No recent tracks yet. Play something on Spotify and check back.
      </p>
    );
  }

  const draggable = Boolean(onSeedDragStart);
  const visible = expanded ? items : items.slice(0, LIST_PREVIEW);

  return (
    <>
      <ol className="track-list">
        {visible.map((track, index) => {
          const seedTrack: SeedTrack = {
            id: track.track_id,
            name: track.name,
            artists: track.artists,
            image_url: track.image_url,
          };
          const selected = selectedIds
            ? isSeedSelected(selectedIds, track.track_id)
            : false;
          return (
            <li
              key={`${track.track_id}-${track.played_at}`}
              className={trackItemClass(selected, draggable)}
              style={{ animationDelay: `${index * 45}ms` }}
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
              <TrackArt imageUrl={track.image_url} label={track.name} />
              <div className="track-main">
                <a
                  href={track.spotify_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="track-title"
                  draggable={false}
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
      <ListExpandToggle
        total={items.length}
        expanded={expanded}
        onToggle={() => setExpanded((value) => !value)}
      />
    </>
  );
}

export function TopTrackList({
  items,
  selectedIds,
  onSeedDragStart,
  onSeedDragEnd,
}: { items: TopTrackItem[] } & SelectableListProps) {
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) {
    return (
      <p className="empty-state">
        No top tracks yet. Keep listening and check back later.
      </p>
    );
  }

  const draggable = Boolean(onSeedDragStart);
  const visible = expanded ? items : items.slice(0, LIST_PREVIEW);

  return (
    <>
      <ol className="track-list">
        {visible.map((track, index) => {
          const seedTrack: SeedTrack = {
            id: track.track_id,
            name: track.name,
            artists: track.artists,
            image_url: track.image_url,
          };
          const selected = selectedIds
            ? isSeedSelected(selectedIds, track.track_id)
            : false;
          return (
            <li
              key={track.track_id}
              className={trackItemClass(selected, draggable)}
              style={{ animationDelay: `${index * 45}ms` }}
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
              <TrackArt imageUrl={track.image_url} label={track.name} />
              <div className="track-main">
                <a
                  href={track.spotify_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="track-title"
                  draggable={false}
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
      <ListExpandToggle
        total={items.length}
        expanded={expanded}
        onToggle={() => setExpanded((value) => !value)}
      />
    </>
  );
}
