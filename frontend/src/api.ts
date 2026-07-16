import type { AuthStatus, RecentlyPlayedResponse } from "./types";

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

export function startSpotifyLogin(): void {
  window.location.assign("/api/auth/spotify/login");
}
