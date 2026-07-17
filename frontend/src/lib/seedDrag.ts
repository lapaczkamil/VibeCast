import type { SeedTrack } from "../types";

export const SEED_DRAG_MIME = "application/x-vibecast-seed";

export function serializeSeed(track: SeedTrack): string {
  return JSON.stringify({
    id: track.id,
    name: track.name,
    artists: track.artists,
    image_url: track.image_url ?? null,
  } satisfies SeedTrack);
}

export function parseSeedDrag(dataTransfer: DataTransfer): SeedTrack | null {
  const raw =
    dataTransfer.getData(SEED_DRAG_MIME) ||
    dataTransfer.getData("text/plain");
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<SeedTrack>;
    if (
      typeof parsed.id !== "string" ||
      typeof parsed.name !== "string" ||
      !Array.isArray(parsed.artists)
    ) {
      return null;
    }
    return {
      id: parsed.id,
      name: parsed.name,
      artists: parsed.artists.filter((a): a is string => typeof a === "string"),
      image_url:
        typeof parsed.image_url === "string" ? parsed.image_url : null,
    };
  } catch {
    return null;
  }
}

export function setSeedDragData(
  dataTransfer: DataTransfer,
  track: SeedTrack,
): void {
  const payload = serializeSeed(track);
  // text/plain is required for reliable cross-element DnD in Chromium/WebKit.
  dataTransfer.setData("text/plain", payload);
  try {
    dataTransfer.setData(SEED_DRAG_MIME, payload);
  } catch {
    // Some browsers reject custom MIME types.
  }
  dataTransfer.effectAllowed = "copyMove";
}
