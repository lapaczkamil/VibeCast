export type PosterEdgeGlow = {
  top: string;
  right: string;
  bottom: string;
  left: string;
  projector: string;
};

type Rgb = { r: number; g: number; b: number };
type Hsl = { h: number; s: number; l: number };

const GLOW_VARS = [
  "--glow-top",
  "--glow-right",
  "--glow-bottom",
  "--glow-left",
  "--projector",
] as const;

const FALLBACK: Rgb = { r: 180, g: 180, b: 190 };

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

function mix(a: Rgb, b: Rgb, t: number): Rgb {
  return {
    r: a.r + (b.r - a.r) * t,
    g: a.g + (b.g - a.g) * t,
    b: a.b + (b.b - a.b) * t,
  };
}

function rgbToHsl({ r, g, b }: Rgb): Hsl {
  const rr = r / 255;
  const gg = g / 255;
  const bb = b / 255;
  const max = Math.max(rr, gg, bb);
  const min = Math.min(rr, gg, bb);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l };

  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h = 0;
  if (max === rr) h = ((gg - bb) / d + (gg < bb ? 6 : 0)) / 6;
  else if (max === gg) h = ((bb - rr) / d + 2) / 6;
  else h = ((rr - gg) / d + 4) / 6;
  return { h: h * 360, s, l };
}

function hslToRgb({ h, s, l }: Hsl): Rgb {
  const hh = ((h % 360) + 360) % 360;
  if (s === 0) {
    const v = l * 255;
    return { r: v, g: v, b: v };
  }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const hk = hh / 360;
  const channel = (t: number) => {
    let x = t;
    if (x < 0) x += 1;
    if (x > 1) x -= 1;
    if (x < 1 / 6) return p + (q - p) * 6 * x;
    if (x < 1 / 2) return q;
    if (x < 2 / 3) return p + (q - p) * (2 / 3 - x) * 6;
    return p;
  };
  return {
    r: channel(hk + 1 / 3) * 255,
    g: channel(hk) * 255,
    b: channel(hk - 1 / 3) * 255,
  };
}

function toGlowRgba(color: Rgb, alpha: number): string {
  const boosted = boostForLed(color);
  return `rgba(${Math.round(boosted.r)}, ${Math.round(boosted.g)}, ${Math.round(boosted.b)}, ${alpha})`;
}

/** Push edge colors toward richer LED-like saturation. */
function boostForLed(color: Rgb): Rgb {
  const hsl = rgbToHsl(color);
  return hslToRgb({
    h: hsl.h,
    s: clamp(hsl.s * 1.1 + 0.04, 0.18, 0.75),
    l: clamp(hsl.l * 0.75 + 0.08, 0.16, 0.48),
  });
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to load poster for glow"));
    img.src = url;
  });
}

function averageEdgeStrip(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  region: "top" | "right" | "bottom" | "left",
): Rgb {
  const strip = Math.max(2, Math.round(Math.min(width, height) * 0.14));
  let sum: Rgb = { r: 0, g: 0, b: 0 };
  let count = 0;

  const include = (x: number, y: number) => {
    const i = (y * width + x) * 4;
    const a = data[i + 3]!;
    if (a < 180) return;
    const color = { r: data[i]!, g: data[i + 1]!, b: data[i + 2]! };
    const { s, l } = rgbToHsl(color);
    // Skip hard letterbox bars, keep muted edge tones.
    if (l < 0.04 || l > 0.96) return;
    const w = 0.35 + s * 0.65;
    sum = {
      r: sum.r + color.r * w,
      g: sum.g + color.g * w,
      b: sum.b + color.b * w,
    };
    count += w;
  };

  if (region === "top") {
    for (let y = 0; y < strip; y += 1) {
      for (let x = 0; x < width; x += 1) include(x, y);
    }
  } else if (region === "bottom") {
    for (let y = height - strip; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) include(x, y);
    }
  } else if (region === "left") {
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < strip; x += 1) include(x, y);
    }
  } else {
    for (let y = 0; y < height; y += 1) {
      for (let x = width - strip; x < width; x += 1) include(x, y);
    }
  }

  if (count <= 0) return FALLBACK;
  return {
    r: sum.r / count,
    g: sum.g / count,
    b: sum.b / count,
  };
}

/**
 * Sample pixels along the poster frame edges (Ambilight / bias-light style).
 */
export async function extractPosterEdgeGlow(
  imageUrl: string,
): Promise<PosterEdgeGlow> {
  const img = await loadImage(imageUrl);
  const size = 96;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas unsupported");

  ctx.drawImage(img, 0, 0, size, size);
  const { data } = ctx.getImageData(0, 0, size, size);

  const top = averageEdgeStrip(data, size, size, "top");
  const right = averageEdgeStrip(data, size, size, "right");
  const bottom = averageEdgeStrip(data, size, size, "bottom");
  const left = averageEdgeStrip(data, size, size, "left");

  const atmosphere = mix(
    mix(top, bottom, 0.5),
    mix(left, right, 0.5),
    0.5,
  );
  const atmHsl = rgbToHsl(atmosphere);
  const soft = hslToRgb({
    h: atmHsl.h,
    s: clamp(atmHsl.s * 0.9, 0.15, 0.8),
    l: clamp(atmHsl.l * 0.5, 0.1, 0.36),
  });

  return {
    top: toGlowRgba(top, 0.42),
    right: toGlowRgba(right, 0.42),
    bottom: toGlowRgba(bottom, 0.38),
    left: toGlowRgba(left, 0.42),
    projector: `rgba(${Math.round(soft.r)}, ${Math.round(soft.g)}, ${Math.round(soft.b)}, 0.2)`,
  };
}

/** @deprecated Prefer extractPosterEdgeGlow — kept for call-site clarity. */
export async function extractPosterPalette(
  imageUrl: string,
): Promise<PosterEdgeGlow> {
  return extractPosterEdgeGlow(imageUrl);
}

export function applyPosterPalette(glow: PosterEdgeGlow): void {
  const root = document.documentElement;
  root.style.setProperty("--glow-top", glow.top);
  root.style.setProperty("--glow-right", glow.right);
  root.style.setProperty("--glow-bottom", glow.bottom);
  root.style.setProperty("--glow-left", glow.left);
  root.style.setProperty("--projector", glow.projector);
  root.dataset.posterTheme = "1";
}

export function clearPosterPalette(): void {
  const root = document.documentElement;
  for (const key of GLOW_VARS) {
    root.style.removeProperty(key);
  }
  // Legacy vars from older palette passes
  for (const key of [
    "--accent",
    "--accent-hot",
    "--accent-warm",
    "--accent-text",
    "--accent-glow",
    "--bg-deep",
    "--bg-mid",
    "--surface",
    "--surface-2",
  ]) {
    root.style.removeProperty(key);
  }
  delete root.dataset.posterTheme;
}
