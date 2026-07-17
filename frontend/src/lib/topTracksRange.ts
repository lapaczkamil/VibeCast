export type TopTracksRange = "week" | "month" | "all";

export const TOP_TRACKS_RANGE_LABELS: Record<TopTracksRange, string> = {
  week: "4 weeks",
  month: "6 months",
  all: "All time",
};

/** Spotify official affinity windows — no overlap with Recently played. */
export function spotifyTimeRangeFor(
  range: TopTracksRange,
): "short_term" | "medium_term" | "long_term" {
  if (range === "week") return "short_term";
  if (range === "month") return "medium_term";
  return "long_term";
}
