/** Upgrade TMDB poster size in an existing image URL. */
export function tmdbPosterUrl(
  url: string | null | undefined,
  size: "w342" | "w500" | "w780" = "w780",
): string | null {
  if (!url) return null;
  return url.replace(/\/t\/p\/w\d+/, `/t/p/${size}`);
}
