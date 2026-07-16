import type { SeedTrack } from "../types";
import { MAX_SEEDS } from "../types";

export function toggleSeed(
  seeds: SeedTrack[],
  track: SeedTrack,
): { seeds: SeedTrack[]; rejected: boolean } {
  const index = seeds.findIndex((s) => s.id === track.id);
  if (index >= 0) {
    return { seeds: seeds.filter((s) => s.id !== track.id), rejected: false };
  }
  if (seeds.length >= MAX_SEEDS) {
    return { seeds, rejected: true };
  }
  return { seeds: [...seeds, track], rejected: false };
}

export function isSeedSelected(
  selectedIds: Set<string> | string[],
  id: string,
): boolean {
  return selectedIds instanceof Set
    ? selectedIds.has(id)
    : selectedIds.includes(id);
}
