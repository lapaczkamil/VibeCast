import { useState, type DragEvent } from "react";
import { parseSeedDrag } from "../lib/seedDrag";
import type { SeedTrack } from "../types";

type MatchDropZoneProps = {
  seeds: SeedTrack[];
  active: boolean;
  disabled: boolean;
  onDropSeed: (track: SeedTrack) => void;
  onRemoveSeed: (id: string) => void;
};

export function MatchDropZone({
  seeds,
  active,
  disabled,
  onDropSeed,
  onRemoveSeed,
}: MatchDropZoneProps) {
  const selected = seeds[0] ?? null;
  const [over, setOver] = useState(false);

  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (disabled) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "copy";
  };

  const onDragEnter = (event: DragEvent<HTMLDivElement>) => {
    if (disabled) return;
    event.preventDefault();
    event.stopPropagation();
    setOver(true);
  };

  const onDragLeave = (event: DragEvent<HTMLDivElement>) => {
    const next = event.relatedTarget;
    if (next instanceof Node && event.currentTarget.contains(next)) return;
    setOver(false);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    if (disabled) return;
    event.preventDefault();
    event.stopPropagation();
    setOver(false);
    const track = parseSeedDrag(event.dataTransfer);
    if (track) onDropSeed(track);
  };

  return (
    <div
      className={
        [
          "match-zone",
          active ? "match-zone--active" : "",
          over ? "match-zone--over" : "",
          disabled ? "match-zone--disabled" : "",
          selected ? "match-zone--filled" : "match-zone--empty",
        ]
          .filter(Boolean)
          .join(" ")
      }
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      role="region"
      aria-label="Drop one track here to match films"
    >
      <div
        className={selected ? "vinyl-card vinyl-card--settled" : "vinyl-card vinyl-card--waiting"}
        key={selected?.id ?? "empty"}
      >
        {selected?.image_url ? (
          <img
            className="vinyl-card-art"
            src={selected.image_url}
            alt=""
            width={112}
            height={112}
            draggable={false}
          />
        ) : (
          <span className="vinyl-card-art vinyl-card-art--empty" aria-hidden="true">
            <span className="vinyl-card-sleeve" />
          </span>
        )}

        <div className="vinyl-card-body">
          {selected ? (
            <>
              <p className="vinyl-card-title">{selected.name}</p>
              <p className="vinyl-card-artists">{selected.artists.join(", ")}</p>
            </>
          ) : (
            <>
              <p className="vinyl-card-title vinyl-card-title--waiting">
                {over || active ? "Release to drop" : "Drop a track"}
              </p>
              <p className="vinyl-card-artists">
                Drag one from Listening
              </p>
            </>
          )}
        </div>

        {selected ? (
          <button
            type="button"
            className="vinyl-card-remove"
            aria-label={`Remove ${selected.name}`}
            onClick={() => onRemoveSeed(selected.id)}
          >
            ×
          </button>
        ) : null}
      </div>
    </div>
  );
}
