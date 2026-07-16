import type {
  AuthStatus,
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SpotifyProfile,
  TopArtistsResponse,
  TopTracksResponse,
} from "./types";

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const res = await fetch("/api/auth/spotify/status");
  if (!res.ok) {
    throw new Error("Failed to load auth status");
  }
  return res.json();
}

export async function fetchRecentlyPlayed(
  limit = 20,
): Promise<RecentlyPlayedResponse> {
  const res = await fetch(`/api/spotify/recently-played?limit=${limit}`);
  if (!res.ok) {
    throw new Error("Failed to load recently played");
  }
  return res.json();
}

export async function fetchMe(): Promise<SpotifyProfile> {
  const res = await fetch("/api/spotify/me");
  if (!res.ok) {
    throw new Error("Failed to load profile");
  }
  return res.json();
}

export async function fetchCurrentlyPlaying(): Promise<CurrentlyPlayingResponse> {
  const res = await fetch("/api/spotify/currently-playing");
  if (!res.ok) {
    throw new Error("Failed to load currently playing");
  }
  return res.json();
}

export async function fetchTopTracks(
  limit = 10,
  timeRange = "medium_term",
): Promise<TopTracksResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    time_range: timeRange,
  });
  const res = await fetch(`/api/spotify/top/tracks?${params}`);
  if (!res.ok) {
    throw new Error("Failed to load top tracks");
  }
  return res.json();
}

export async function fetchTopArtists(
  limit = 10,
  timeRange = "medium_term",
): Promise<TopArtistsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    time_range: timeRange,
  });
  const res = await fetch(`/api/spotify/top/artists?${params}`);
  if (!res.ok) {
    throw new Error("Failed to load top artists");
  }
  return res.json();
}

export async function logoutSpotify(): Promise<AuthStatus> {
  const res = await fetch("/api/auth/spotify/logout", { method: "POST" });
  if (!res.ok) {
    throw new Error("Failed to log out");
  }
  return res.json();
}

export function startSpotifyLogin(): void {
  window.location.assign("/api/auth/spotify/login");
}
