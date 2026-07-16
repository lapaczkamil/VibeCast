import { useEffect, useState } from "react";
import { searchSpotifyTracks } from "../api";
import { isSeedSelected } from "../lib/seeds";
import type {
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SectionState,
  SeedTrack,
  TopTracksResponse,
  TrackSearchItem,
} from "../types";
import { MAX_SEEDS } from "../types";
import { Drawer } from "./Drawer";
import { DashboardSection } from "./DashboardSection";
import { NowPlaying } from "./NowPlaying";
import { RecentTrackList, TopTrackList } from "./TrackList";

type ListeningDrawerProps = {
  open: boolean;
  onClose: () => void;
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  recentlyPlayed: SectionState<RecentlyPlayedResponse>;
  topTracks: SectionState<TopTracksResponse>;
  seeds: SeedTrack[];
  onToggleSeed: (track: SeedTrack) => void;
  onClearSeeds: () => void;
  limitHint: string | null;
  onRetryCurrentlyPlaying: () => void;
  onRetryRecentlyPlayed: () => void;
  onRetryTopTracks: () => void;
};

function SearchResultRow({
  track,
  selectedIds,
  onToggle,
  disabledAdd,
}: {
  track: TrackSearchItem;
  selectedIds: Set<string>;
  onToggle: (track: SeedTrack) => void;
  disabledAdd: boolean;
}) {
  const seedTrack: SeedTrack = {
    id: track.id,
    name: track.name,
    artists: track.artists,
  };
  const selected = isSeedSelected(selectedIds, track.id);

  return (
    <li className="track-item track-item--search">
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
        onClick={() => onToggle(seedTrack)}
      />
      {track.image_url ? (
        <img
          src={track.image_url}
          alt=""
          className="search-track-art"
          width={40}
          height={40}
        />
      ) : (
        <span className="search-track-art search-track-art--placeholder" aria-hidden="true" />
      )}
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
}

export function ListeningDrawer(props: ListeningDrawerProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<TrackSearchItem[]>([]);

  const selectedIds = new Set(props.seeds.map((s) => s.id));
  const disabledAdd = props.seeds.length >= MAX_SEEDS;

  useEffect(() => {
    if (!props.open) {
      setSearchQuery("");
      setDebouncedQuery("");
      setSearchResults([]);
      setSearchError(null);
      setSearchLoading(false);
    }
  }, [props.open]);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQuery(searchQuery.trim()), 300);
    return () => window.clearTimeout(id);
  }, [searchQuery]);

  useEffect(() => {
    if (!debouncedQuery) {
      setSearchResults([]);
      setSearchError(null);
      setSearchLoading(false);
      return;
    }

    let cancelled = false;
    setSearchLoading(true);
    setSearchError(null);

    void searchSpotifyTracks(debouncedQuery, 10)
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
  }, [debouncedQuery]);

  const runSearchNow = () => {
    setDebouncedQuery(searchQuery.trim());
  };

  return (
    <Drawer title="Listening" open={props.open} onClose={props.onClose}>
      <div className="listening-drawer">
        <div className="listening-drawer-scroll">
          <section className="listening-search" aria-label="Search Spotify tracks">
            <label className="listening-search-label" htmlFor="track-search">
              Search tracks
            </label>
            <div className="listening-search-row">
              <input
                id="track-search"
                type="search"
                className="listening-search-input"
                placeholder="Song or artist…"
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
            {debouncedQuery && !searchLoading && searchResults.length === 0 && !searchError ? (
              <p className="empty-state">No tracks found.</p>
            ) : null}
            {searchResults.length > 0 ? (
              <ol className="track-list track-list--search">
                {searchResults.map((track) => (
                  <SearchResultRow
                    key={track.id}
                    track={track}
                    selectedIds={selectedIds}
                    onToggle={props.onToggleSeed}
                    disabledAdd={disabledAdd}
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
                onToggle={props.onToggleSeed}
                disabledAdd={disabledAdd}
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
                onToggle={props.onToggleSeed}
                disabledAdd={disabledAdd}
              />
            )}
          </DashboardSection>

          <DashboardSection
            title="Top tracks"
            state={props.topTracks}
            onRetry={props.onRetryTopTracks}
          >
            {(data) => (
              <TopTrackList
                items={data.items}
                selectedIds={selectedIds}
                onToggle={props.onToggleSeed}
                disabledAdd={disabledAdd}
              />
            )}
          </DashboardSection>
        </div>

        <footer className="listening-footer">
          {props.limitHint ? (
            <p className="listening-footer-hint" role="status">
              {props.limitHint}
            </p>
          ) : null}
          <div className="listening-footer-row">
            <span className="listening-footer-count">
              Seeds: {props.seeds.length}/{MAX_SEEDS}
            </span>
            <button
              type="button"
              className="cta cta--ghost listening-footer-clear"
              disabled={props.seeds.length === 0}
              onClick={props.onClearSeeds}
            >
              Clear
            </button>
          </div>
        </footer>
      </div>
    </Drawer>
  );
}
