/** Wrap-around next index; returns 0 if length <= 0. */
export function nextIndex(current: number, length: number): number {
  if (length <= 0) return 0;
  return (current + 1) % length;
}

/** Wrap-around previous index; returns 0 if length <= 0. */
export function prevIndex(current: number, length: number): number {
  if (length <= 0) return 0;
  return (current - 1 + length) % length;
}
