import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchAuthStatus,
  fetchCurrentlyPlaying,
  fetchRateLimitStatus,
  fetchRecentlyPlayed,
  fetchSpotifySession,
  fetchTopTracks,
  logoutSpotify,
  startSpotifyLogin,
} from "./api";
import { AppChrome } from "./components/AppChrome";
import { AlbumConveyor } from "./components/AlbumConveyor";
import { ListeningPanel } from "./components/ListeningPanel";
import { RecommendStage } from "./components/RecommendStage";
import { SearchDrawer } from "./components/SearchDrawer";
import { AudioMeters } from "./components/AudioMeters";
import type {
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SectionState,
  SeedTrack,
  SpotifyProfile,
  TopTracksResponse,
} from "./types";
import { addSeed } from "./lib/seeds";
import {
  spotifyTimeRangeFor,
  type TopTracksRange,
} from "./lib/topTracksRange";

function authErrorFromSearch(search: string): boolean {
  return new URLSearchParams(search).get("auth_error") === "1";
}

const idleSection = <T,>(): SectionState<T> => ({ status: "idle" });
const loadingSection = <T,>(): SectionState<T> => ({ status: "loading" });

const PLACEHOLDER_PROFILE: SpotifyProfile = {
  id: "local",
  display_name: "Spotify",
  image_url: null,
  country: null,
  product: null,
};

/** Manual refresh cooldown — avoids burning Development Mode quota. */
const REFRESH_COOLDOWN_MS = 5 * 60_000;
/** Now-playing poll — slightly above backend/client cache TTL. */
const NOW_PLAYING_POLL_MS = 25_000;
/** Recently-played steady refresh. */
const RECENTLY_PLAYED_POLL_MS = 3 * 60_000;

let sessionPromise: Promise<void> | null = null;

function parseWaitSeconds(message: string): number {
  const match = message.match(/about (\d+)s/);
  if (match) return Number(match[1]);
  return 300;
}

export default function App() {
  const [authError] = useState(() =>
    authErrorFromSearch(window.location.search),
  );
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authFetchError, setAuthFetchError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [drawer, setDrawer] = useState<null | "search">(null);
  const [listeningOpen, setListeningOpen] = useState(false);
  const [seedDragging, setSeedDragging] = useState(false);
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 899px)").matches,
  );

  const [me, setMe] = useState<SectionState<SpotifyProfile>>({
    status: "ok",
    data: PLACEHOLDER_PROFILE,
  });
  const [currentlyPlaying, setCurrentlyPlaying] =
    useState<SectionState<CurrentlyPlayingResponse>>({
      status: "ok",
      data: { is_playing: false, track: null },
    });
  const [recentlyPlayed, setRecentlyPlayed] =
    useState<SectionState<RecentlyPlayedResponse>>(idleSection);
  const [topTracks, setTopTracks] =
    useState<SectionState<TopTracksResponse>>(idleSection);
  const [topTracksRange, setTopTracksRange] =
    useState<TopTracksRange>("month");
  const topTracksCacheRef = useRef<
    Partial<Record<TopTracksRange, TopTracksResponse>>
  >({});
  const [seeds, setSeeds] = useState<SeedTrack[]>([]);
  const [blockedUntil, setBlockedUntil] = useState<number | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<number | null>(null);
  const sessionRunRef = useRef(0);
  const recentlyStatusRef = useRef(recentlyPlayed.status);
  const topStatusRef = useRef(topTracks.status);
  const blockedUntilRef = useRef(blockedUntil);
  const lastRefreshAtRef = useRef(lastRefreshAt);
  recentlyStatusRef.current = recentlyPlayed.status;
  topStatusRef.current = topTracks.status;
  blockedUntilRef.current = blockedUntil;
  lastRefreshAtRef.current = lastRefreshAt;

  const applyRateLimit = useCallback((message: string) => {
    const waitSec = parseWaitSeconds(message);
    setBlockedUntil(Date.now() + waitSec * 1000);
  }, []);

  const loadSession = useCallback(
    async (opts?: { refresh?: boolean }) => {
      if (sessionPromise && !opts?.refresh) {
        return sessionPromise;
      }

      const blocked = blockedUntilRef.current;
      if (blocked && Date.now() < blocked) {
        return;
      }

      const lastRefresh = lastRefreshAtRef.current;
      if (opts?.refresh && lastRefresh) {
        const elapsed = Date.now() - lastRefresh;
        if (elapsed < REFRESH_COOLDOWN_MS) {
          return;
        }
      }

      try {
        const status = await fetchRateLimitStatus();
        if (status.blocked && status.remaining_seconds > 0) {
          setBlockedUntil(Date.now() + status.remaining_seconds * 1000);
          return;
        }
      } catch {
        // ignore
      }

      const runId = ++sessionRunRef.current;
      const cancelled = () => runId !== sessionRunRef.current;

      const work = (async () => {
        if (recentlyStatusRef.current !== "ok" || opts?.refresh) {
          setRecentlyPlayed(loadingSection());
        }
        if (topStatusRef.current !== "ok" || opts?.refresh) {
          setTopTracks(loadingSection());
        }

        try {
          const data = await fetchSpotifySession({
            limit: 30,
            timeRange: "medium_term",
            refresh: opts?.refresh === true,
          });
          if (cancelled()) return;

          setMe({ status: "ok", data: data.me });
          setRecentlyPlayed({ status: "ok", data: data.recently_played });
          topTracksCacheRef.current.month = data.top_tracks;
          setTopTracksRange("month");
          setTopTracks({ status: "ok", data: data.top_tracks });
          setCurrentlyPlaying({
            status: "ok",
            data: data.currently_playing,
          });
          setBlockedUntil(null);
          if (opts?.refresh) {
            setLastRefreshAt(Date.now());
          }
        } catch (err: unknown) {
          if (cancelled()) return;
          const message =
            err instanceof Error ? err.message : "Failed to load Spotify data";
          if (message.toLowerCase().includes("rate limit")) {
            applyRateLimit(message);
          }
          if (recentlyStatusRef.current !== "ok") {
            setRecentlyPlayed({ status: "error", error: message });
          }
          if (topStatusRef.current !== "ok") {
            setTopTracks({ status: "error", error: message });
          }
        }
      })();

      sessionPromise = work.finally(() => {
        sessionPromise = null;
      });
      return sessionPromise;
    },
    [applyRateLimit],
  );

  const loadAuth = useCallback(async () => {
    setAuthLoading(true);
    setAuthFetchError(null);

    try {
      const status = await fetchAuthStatus();
      setAuthenticated(status.authenticated);
      if (status.authenticated) {
        void loadSession();
      }
    } catch {
      setAuthFetchError("Could not reach VibeCast. Is the backend running?");
      setAuthenticated(null);
    } finally {
      setAuthLoading(false);
    }
  }, [loadSession]);

  const handleLogout = useCallback(async () => {
    setLoggingOut(true);
    try {
      await logoutSpotify();
    } catch {
      // Still return to logged-out UI if the session was cleared server-side.
    } finally {
      setLoggingOut(false);
      setAuthenticated(false);
      setDrawer(null);
      setListeningOpen(false);
      setSeedDragging(false);
      setMe({ status: "ok", data: PLACEHOLDER_PROFILE });
      setCurrentlyPlaying({
        status: "ok",
        data: { is_playing: false, track: null },
      });
      setRecentlyPlayed(idleSection());
      setTopTracks(idleSection());
      setTopTracksRange("month");
      topTracksCacheRef.current = {};
      setSeeds([]);
      setBlockedUntil(null);
      setLastRefreshAt(null);
      sessionRunRef.current += 1;
    }
  }, []);

  const handleDropSeed = useCallback((track: SeedTrack) => {
    setSeeds((current) => {
      const { seeds: next } = addSeed(current, track);
      return next;
    });
    setSeedDragging(false);
    setListeningOpen(false);
  }, []);

  const handleSeedDragStart = useCallback((_track: SeedTrack) => {
    setSeedDragging(true);
  }, []);

  const handleSeedDragEnd = useCallback(() => {
    setSeedDragging(false);
  }, []);

  const handleTopTracksRangeChange = useCallback(
    async (range: TopTracksRange) => {
      setTopTracksRange(range);

      const cached = topTracksCacheRef.current[range];
      if (cached) {
        setTopTracks({ status: "ok", data: cached });
        return;
      }

      const spotifyRange = spotifyTimeRangeFor(range);
      setTopTracks(loadingSection());
      try {
        const data = await fetchTopTracks(30, spotifyRange);
        topTracksCacheRef.current[range] = data;
        setTopTracks({ status: "ok", data });
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load top tracks";
        setTopTracks({ status: "error", error: message });
        if (/429|rate limit/i.test(message)) {
          applyRateLimit(message);
        }
      }
    },
    [applyRateLimit],
  );

  const handleClearSeeds = useCallback(() => {
    setSeeds([]);
  }, []);

  const handleRemoveSeed = useCallback((id: string) => {
    setSeeds((current) => current.filter((s) => s.id !== id));
  }, []);

  const closeDrawer = useCallback(() => setDrawer(null), []);
  const closeListening = useCallback(() => setListeningOpen(false), []);
  const toggleListening = useCallback(
    () => setListeningOpen((open) => !open),
    [],
  );

  const refreshCurrentlyPlaying = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (blockedUntilRef.current && Date.now() < blockedUntilRef.current) {
        return;
      }
      if (!opts?.silent) {
        setCurrentlyPlaying(loadingSection());
      }
      try {
        const data = await fetchCurrentlyPlaying();
        setCurrentlyPlaying({ status: "ok", data });
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load now playing";
        if (message.toLowerCase().includes("rate limit")) {
          applyRateLimit(message);
          // Keep last good snapshot — don't wipe now playing on 429.
          return;
        }
        if (opts?.silent) {
          return;
        }
        setCurrentlyPlaying({ status: "error", error: message });
      }
    },
    [applyRateLimit],
  );

  const refreshRecentlyPlayed = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (blockedUntilRef.current && Date.now() < blockedUntilRef.current) {
        return;
      }
      if (!opts?.silent) {
        setRecentlyPlayed(loadingSection());
      }
      try {
        const data = await fetchRecentlyPlayed(30);
        setRecentlyPlayed({ status: "ok", data });
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load recently played";
        if (message.toLowerCase().includes("rate limit")) {
          applyRateLimit(message);
          return;
        }
        if (opts?.silent) {
          return;
        }
        setRecentlyPlayed({ status: "error", error: message });
      }
    },
    [applyRateLimit],
  );

  const refreshCurrentlyPlayingRef = useRef(refreshCurrentlyPlaying);
  refreshCurrentlyPlayingRef.current = refreshCurrentlyPlaying;
  const refreshRecentlyPlayedRef = useRef(refreshRecentlyPlayed);
  refreshRecentlyPlayedRef.current = refreshRecentlyPlayed;

  useEffect(() => {
    if (!authenticated) return;

    const tickNowPlaying = () => {
      if (document.visibilityState === "hidden") return;
      if (sessionPromise) return;
      if (blockedUntilRef.current && Date.now() < blockedUntilRef.current) {
        return;
      }
      void refreshCurrentlyPlayingRef.current({ silent: true });
    };

    const tickRecentlyPlayed = () => {
      if (document.visibilityState === "hidden") return;
      if (sessionPromise) return;
      if (blockedUntilRef.current && Date.now() < blockedUntilRef.current) {
        return;
      }
      void refreshRecentlyPlayedRef.current({ silent: true });
    };

    const nowId = window.setInterval(tickNowPlaying, NOW_PLAYING_POLL_MS);
    const recentId = window.setInterval(
      tickRecentlyPlayed,
      RECENTLY_PLAYED_POLL_MS,
    );

    return () => {
      window.clearInterval(nowId);
      window.clearInterval(recentId);
    };
  }, [authenticated]);

  useEffect(() => {
    if (authError) {
      const url = new URL(window.location.href);
      url.searchParams.delete("auth_error");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
    void loadAuth();
  }, [authError, loadAuth]);

  useEffect(() => {
    if (!blockedUntil) return;
    const id = window.setInterval(() => {
      if (Date.now() >= blockedUntil) {
        setBlockedUntil(null);
      }
    }, 1000);
    return () => window.clearInterval(id);
  }, [blockedUntil]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 899px)");
    const onChange = () => setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (!listeningOpen || drawer !== null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setListeningOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [listeningOpen, drawer]);

  if (authLoading) {
    return (
      <div className="app">
        <AudioMeters active />
        <main className="shell shell--center">
          <p className="status-message">Loading…</p>
        </main>
      </div>
    );
  }

  if (authFetchError) {
    return (
      <div className="app">
        <AudioMeters active />
        <main className="shell shell--center">
          <p className="status-message status-message--error">{authFetchError}</p>
          <button type="button" className="cta cta--ghost" onClick={loadAuth}>
            Try again
          </button>
        </main>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="app">
        <AudioMeters active />
        <main className="shell shell--landing">
          <h1 className="brand brand--hero">VibeCast</h1>
          <p className="subtitle">Films tuned to your signal.</p>
          <p className="landing-lede">
            Plug into Spotify. Read the mood in your tracks. Match it to cinema.
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

  const isPlaying =
    currentlyPlaying.status === "ok" &&
    currentlyPlaying.data?.is_playing === true;

  const recentCoverUrls =
    recentlyPlayed.status === "ok"
      ? recentlyPlayed.data!.items
          .map((item) => item.image_url)
          .filter((url): url is string => Boolean(url))
      : [];

  return (
    <div
      className={
        [
          "app",
          "app--stage",
          drawer ? "app--drawer-open" : "",
          listeningOpen ? "app--listening-open" : "",
          seedDragging ? "app--seed-dragging" : "",
        ]
          .filter(Boolean)
          .join(" ")
      }
    >
      <AudioMeters active={isPlaying} />
      <AlbumConveyor imageUrls={recentCoverUrls} />
      <AppChrome
        profile={me}
        currentlyPlaying={currentlyPlaying}
        loggingOut={loggingOut}
        onLogout={() => void handleLogout()}
        listeningOpen={listeningOpen}
        onToggleListening={toggleListening}
        onOpenSearch={() => setDrawer("search")}
      />
      <button
        type="button"
        className="listening-panel-backdrop"
        aria-label="Close Listening"
        onClick={closeListening}
      />
      <div className="stage-workspace">
        <ListeningPanel
          currentlyPlaying={currentlyPlaying}
          recentlyPlayed={recentlyPlayed}
          topTracks={topTracks}
          topTracksRange={topTracksRange}
          onTopTracksRangeChange={(range) => void handleTopTracksRangeChange(range)}
          seeds={seeds}
          onClearSeeds={handleClearSeeds}
          onSeedDragStart={handleSeedDragStart}
          onSeedDragEnd={handleSeedDragEnd}
          onRetryCurrentlyPlaying={() => void refreshCurrentlyPlaying()}
          onRetryRecentlyPlayed={() => void refreshRecentlyPlayed()}
          onRetryTopTracks={() => void handleTopTracksRangeChange(topTracksRange)}
          inert={narrow && !listeningOpen}
        />
        <main className="shell shell--stage">
          <RecommendStage
            drawerOpen={drawer !== null || listeningOpen}
            seedDragging={seedDragging}
            seeds={seeds}
            isPlaying={isPlaying}
            onDropSeed={handleDropSeed}
            onRemoveSeed={handleRemoveSeed}
          />
        </main>
      </div>
      <SearchDrawer open={drawer === "search"} onClose={closeDrawer} />
    </div>
  );
}
