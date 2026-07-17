import type { SeedTrack } from "../types";

export function toggleSeed(
  seeds: SeedTrack[],
  track: SeedTrack,
): { seeds: SeedTrack[]; rejected: boolean } {
  const index = seeds.findIndex((s) => s.id === track.id);
  if (index >= 0) {
    return { seeds: [], rejected: false };
  }
  // Single-seed mode: selecting another track replaces the current one.
  return { seeds: [track], rejected: false };
}

export function addSeed(
  seeds: SeedTrack[],
  track: SeedTrack,
): { seeds: SeedTrack[]; rejected: boolean; already: boolean } {
  if (seeds.some((s) => s.id === track.id)) {
    return { seeds, rejected: false, already: true };
  }
  // Replace any existing selection.
  return { seeds: [track], rejected: false, already: false };
}

export function isSeedSelected(
  selectedIds: Set<string> | string[],
  id: string,
): boolean {
  return selectedIds instanceof Set
    ? selectedIds.has(id)
    : selectedIds.includes(id);
}
