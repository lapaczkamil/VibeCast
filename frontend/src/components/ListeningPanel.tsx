import { useEffect, useState } from "react";
import { searchSpotifyTracks } from "../api";
import { setSeedDragData } from "../lib/seedDrag";
import { isSeedSelected } from "../lib/seeds";
import {
  TOP_TRACKS_RANGE_LABELS,
  type TopTracksRange,
} from "../lib/topTracksRange";
import type {
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SectionState,
  SeedTrack,
  TopTracksResponse,
  TrackSearchItem,
} from "../types";
import { DashboardSection } from "./DashboardSection";
import { NowPlaying } from "./NowPlaying";
import { RecentTrackList, TopTrackList } from "./TrackList";

export type ListeningPanelProps = {
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  recentlyPlayed: SectionState<RecentlyPlayedResponse>;
  topTracks: SectionState<TopTracksResponse>;
  topTracksRange: TopTracksRange;
  onTopTracksRangeChange: (range: TopTracksRange) => void;
  seeds: SeedTrack[];
  onClearSeeds: () => void;
  onSeedDragStart: (track: SeedTrack) => void;
  onSeedDragEnd: () => void;
  onRetryCurrentlyPlaying: () => void;
  onRetryRecentlyPlayed: () => void;
  onRetryTopTracks: () => void;
  /** Mobile overlay closed — remove from tab order and accessibility tree. */
  inert?: boolean;
};

function SearchResultRow({
  track,
  selectedIds,
  onSeedDragStart,
  onSeedDragEnd,
}: {
  track: TrackSearchItem;
  selectedIds: Set<string>;
  onSeedDragStart: (track: SeedTrack) => void;
  onSeedDragEnd: () => void;
}) {
  const seedTrack: SeedTrack = {
    id: track.id,
    name: track.name,
    artists: track.artists,
    image_url: track.image_url,
  };
  const selected = isSeedSelected(selectedIds, track.id);

  return (
    <li
      className={
        selected
          ? "track-item track-item--search track-item--draggable track-item--selected"
          : "track-item track-item--search track-item--draggable"
      }
      draggable
      onDragStart={(event) => {
        setSeedDragData(event.dataTransfer, seedTrack);
        onSeedDragStart(seedTrack);
      }}
      onDragEnd={onSeedDragEnd}
      title="Drop on the match slot"
    >
      {track.image_url ? (
        <img
          src={track.image_url}
          alt=""
          className="search-track-art"
          width={40}
          height={40}
          draggable={false}
        />
      ) : (
        <span
          className="search-track-art search-track-art--placeholder"
          aria-hidden="true"
        />
      )}
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
}

export function ListeningPanel(props: ListeningPanelProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<TrackSearchItem[]>([]);

  const selectedIds = new Set(props.seeds.map((s) => s.id));

  useEffect(() => {
    if (!activeQuery) {
      setSearchResults([]);
      setSearchError(null);
      setSearchLoading(false);
      return;
    }

    let cancelled = false;
    setSearchLoading(true);
    setSearchError(null);

    void searchSpotifyTracks(activeQuery, 10)
      .then((data) => {
        if (!cancelled) {
          setSearchResults(data.items);
          setSearchLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSearchError(
            err instanceof Error ? err.message : "Track search failed",
          );
          setSearchResults([]);
          setSearchLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeQuery]);

  const runSearchNow = () => {
    setActiveQuery(searchQuery.trim());
  };

  const hidden = props.inert === true;

  return (
    <aside
      id="listening-panel"
      className="listening-panel"
      aria-label="Listening"
      {...(hidden ? { inert: true, "aria-hidden": true } : {})}
    >
      <div className="listening-panel-body">
        <div className="listening-panel-scroll">
          <section className="listening-search" aria-label="Search Spotify tracks">
            <label className="listening-search-label" htmlFor="track-search">
              Search tracks
            </label>
            <div className="listening-search-row">
              <input
                id="track-search"
                type="search"
                className="listening-search-input"
                placeholder="Song or artist… (press Enter)"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    runSearchNow();
                  }
                }}
              />
            </div>
            {searchLoading ? (
              <p className="section-status">Searching…</p>
            ) : null}
            {searchError ? (
              <p className="status-message status-message--error" role="alert">
                {searchError}
              </p>
            ) : null}
            {activeQuery && !searchLoading && searchResults.length === 0 && !searchError ? (
              <p className="empty-state">No tracks found.</p>
            ) : null}
            {searchResults.length > 0 ? (
              <ol className="track-list track-list--search">
                {searchResults.map((track) => (
                  <SearchResultRow
                    key={track.id}
                    track={track}
                    selectedIds={selectedIds}
                    onSeedDragStart={props.onSeedDragStart}
                    onSeedDragEnd={props.onSeedDragEnd}
                  />
                ))}
              </ol>
            ) : null}
          </section>

          <DashboardSection
            title="Now playing"
            state={props.currentlyPlaying}
            onRetry={props.onRetryCurrentlyPlaying}
          >
            {(data) => (
              <NowPlaying
                data={data}
                selectedIds={selectedIds}
                onSeedDragStart={props.onSeedDragStart}
                onSeedDragEnd={props.onSeedDragEnd}
              />
            )}
          </DashboardSection>

          <DashboardSection
            title="Recently played"
            state={props.recentlyPlayed}
            onRetry={props.onRetryRecentlyPlayed}
          >
            {(data) => (
              <RecentTrackList
                items={data.items}
                selectedIds={selectedIds}
                onSeedDragStart={props.onSeedDragStart}
                onSeedDragEnd={props.onSeedDragEnd}
              />
            )}
          </DashboardSection>

          <section className="dashboard-section" aria-label="Top tracks">
            <h2 className="section-title">Top tracks</h2>
            <div
              className="top-range-filters"
              role="group"
              aria-label="Top tracks time range"
            >
              {(Object.keys(TOP_TRACKS_RANGE_LABELS) as TopTracksRange[]).map(
                (range) => (
                  <button
                    key={range}
                    type="button"
                    className={
                      props.topTracksRange === range
                        ? "top-range-btn top-range-btn--active"
                        : "top-range-btn"
                    }
                    aria-pressed={props.topTracksRange === range}
                    onClick={() => props.onTopTracksRangeChange(range)}
                  >
                    {TOP_TRACKS_RANGE_LABELS[range]}
                  </button>
                ),
              )}
            </div>
            {props.topTracks.status === "idle" ? (
              <p className="status-message section-status">Not loaded yet.</p>
            ) : null}
            {props.topTracks.status === "loading" ? (
              <p className="status-message section-status">Loading…</p>
            ) : null}
            {props.topTracks.status === "error" ? (
              <div className="section-error">
                <p className="status-message status-message--error">
                  {props.topTracks.error ?? "Something went wrong."}
                </p>
                <button
                  type="button"
                  className="cta cta--ghost"
                  onClick={props.onRetryTopTracks}
                >
                  Try again
                </button>
              </div>
            ) : null}
            {props.topTracks.status === "ok" && props.topTracks.data ? (
              <TopTrackList
                key={props.topTracksRange}
                items={props.topTracks.data.items}
                selectedIds={selectedIds}
                onSeedDragStart={props.onSeedDragStart}
                onSeedDragEnd={props.onSeedDragEnd}
              />
            ) : null}
          </section>
        </div>

        <footer className="listening-footer">
          <div className="listening-footer-row">
            <p className="listening-footer-count">
              <span className="listening-footer-count-label">Track</span>
              <span className="listening-footer-count-value" aria-live="polite">
                {props.seeds.length === 0
                  ? "None"
                  : props.seeds[0]?.name ?? "Selected"}
              </span>
            </p>
            <button
              type="button"
              className="chrome-btn listening-footer-clear"
              disabled={props.seeds.length === 0}
              onClick={props.onClearSeeds}
            >
              Clear
            </button>
          </div>
        </footer>
      </div>
    </aside>
  );
}
