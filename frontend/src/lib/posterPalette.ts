export type PosterPalette = {
  accent: string;
  accentHot: string;
  accentWarm: string;
  accentText: string;
  accentGlow: string;
  projector: string;
  bgDeep: string;
  bgMid: string;
  surface: string;
  surface2: string;
};

type Rgb = { r: number; g: number; b: number };
type Hsl = { h: number; s: number; l: number };

const PALETTE_VARS = [
  "--accent",
  "--accent-hot",
  "--accent-warm",
  "--accent-text",
  "--accent-glow",
  "--projector",
  "--bg-deep",
  "--bg-mid",
  "--surface",
  "--surface-2",
] as const;

const FALLBACK: Rgb = { r: 29, g: 185, b: 84 };

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

function rgbToHex({ r, g, b }: Rgb): string {
  return `#${[r, g, b]
    .map((v) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0"))
    .join("")}`;
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

function relativeLuminance({ r, g, b }: Rgb): number {
  const lin = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lin[0]! + 0.7152 * lin[1]! + 0.0722 * lin[2]!;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to load poster for palette"));
    img.src = url;
  });
}

type Bucket = {
  count: number;
  weight: number;
  sum: Rgb;
};

/**
 * Dominant hue from the poster core (not edges), weighted by how often
 * that hue appears × how saturated it is — closer to what the eye reads.
 */
function dominantFromPixels(data: Uint8ClampedArray): Rgb {
  const bins = 24;
  const buckets: Bucket[] = Array.from({ length: bins }, () => ({
    count: 0,
    weight: 0,
    sum: { r: 0, g: 0, b: 0 },
  }));

  let mutedSum: Rgb = { r: 0, g: 0, b: 0 };
  let mutedCount = 0;

  for (let i = 0; i < data.length; i += 4) {
    const a = data[i + 3]!;
    if (a < 200) continue;

    const color = { r: data[i]!, g: data[i + 1]!, b: data[i + 2]! };
    const { h, s, l } = rgbToHsl(color);

    // Skip near-black / near-white letterbox and text blocks.
    if (l < 0.08 || l > 0.92) continue;

    if (s < 0.18) {
      mutedSum = {
        r: mutedSum.r + color.r,
        g: mutedSum.g + color.g,
        b: mutedSum.b + color.b,
      };
      mutedCount += 1;
      continue;
    }

    // Prefer midtones — poster key art usually lives here.
    const toneBias = 1 - Math.min(1, Math.abs(l - 0.45) / 0.45);
    const idx = Math.min(bins - 1, Math.floor((h / 360) * bins));
    const bucket = buckets[idx]!;
    const w = s * (0.55 + toneBias * 0.45);
    bucket.count += 1;
    bucket.weight += w;
    bucket.sum.r += color.r * w;
    bucket.sum.g += color.g * w;
    bucket.sum.b += color.b * w;
  }

  let best: Bucket | null = null;
  for (const bucket of buckets) {
    if (bucket.count < 4) continue;
    if (!best || bucket.weight > best.weight) best = bucket;
  }

  if (best && best.weight > 0) {
    return {
      r: best.sum.r / best.weight,
      g: best.sum.g / best.weight,
      b: best.sum.b / best.weight,
    };
  }

  if (mutedCount > 0) {
    return {
      r: mutedSum.r / mutedCount,
      g: mutedSum.g / mutedCount,
      b: mutedSum.b / mutedCount,
    };
  }

  return FALLBACK;
}

/** Keep hue/sat from the poster; only nudge lightness so UI stays usable. */
function uiAccentFromSource(source: Rgb): Rgb {
  const hsl = rgbToHsl(source);
  const s = clamp(hsl.s * 1.08, 0.35, 0.92);
  const l = clamp(hsl.l, 0.38, 0.62);
  return hslToRgb({ h: hsl.h, s, l });
}

function readableText(accent: Rgb): Rgb {
  const hsl = rgbToHsl(accent);
  if (relativeLuminance(accent) < 0.4) {
    return hslToRgb({
      h: hsl.h,
      s: clamp(hsl.s, 0.35, 0.85),
      l: clamp(hsl.l + 0.22, 0.55, 0.72),
    });
  }
  return hslToRgb({
    h: hsl.h,
    s: clamp(hsl.s, 0.3, 0.8),
    l: clamp(hsl.l - 0.08, 0.32, 0.55),
  });
}

/** Sample the poster core (crop edges — often black bars / frames). */
export async function extractPosterPalette(
  imageUrl: string,
): Promise<PosterPalette> {
  const img = await loadImage(imageUrl);
  const size = 72;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas unsupported");

  const crop = 0.12;
  const sx = img.naturalWidth * crop;
  const sy = img.naturalHeight * crop;
  const sw = img.naturalWidth * (1 - crop * 2);
  const sh = img.naturalHeight * (1 - crop * 2);
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, size, size);

  const { data } = ctx.getImageData(0, 0, size, size);
  const source = dominantFromPixels(data);
  const accentRgb = uiAccentFromSource(source);
  const sourceHsl = rgbToHsl(source);

  // Atmosphere uses the real poster color (not the UI-lifted accent).
  const atmosphere = hslToRgb({
    h: sourceHsl.h,
    s: clamp(sourceHsl.s * 0.95, 0.2, 0.85),
    l: clamp(sourceHsl.l * 0.55, 0.12, 0.38),
  });

  const white = { r: 255, g: 255, b: 255 };
  const black = { r: 0, g: 0, b: 0 };
  const accentHot = mix(accentRgb, white, 0.18);
  const accentWarm = mix(accentRgb, black, 0.18);
  const text = readableText(accentRgb);

  const ar = Math.round(accentRgb.r);
  const ag = Math.round(accentRgb.g);
  const ab = Math.round(accentRgb.b);
  const sr = Math.round(atmosphere.r);
  const sg = Math.round(atmosphere.g);
  const sb = Math.round(atmosphere.b);

  const baseDeep = { r: 12, g: 12, b: 12 };
  const baseMid = { r: 20, g: 20, b: 20 };
  const baseSurface = { r: 22, g: 22, b: 22 };
  const baseSurface2 = { r: 36, g: 36, b: 36 };

  return {
    accent: rgbToHex(accentRgb),
    accentHot: rgbToHex(accentHot),
    accentWarm: rgbToHex(accentWarm),
    accentText: rgbToHex(text),
    accentGlow: `rgba(${ar}, ${ag}, ${ab}, 0.4)`,
    projector: `rgba(${sr}, ${sg}, ${sb}, 0.42)`,
    bgDeep: rgbToHex(mix(baseDeep, atmosphere, 0.42)),
    bgMid: rgbToHex(mix(baseMid, atmosphere, 0.36)),
    surface: rgbToHex(mix(baseSurface, atmosphere, 0.28)),
    surface2: rgbToHex(mix(baseSurface2, atmosphere, 0.32)),
  };
}

export function applyPosterPalette(palette: PosterPalette): void {
  const root = document.documentElement;
  root.style.setProperty("--accent", palette.accent);
  root.style.setProperty("--accent-hot", palette.accentHot);
  root.style.setProperty("--accent-warm", palette.accentWarm);
  root.style.setProperty("--accent-text", palette.accentText);
  root.style.setProperty("--accent-glow", palette.accentGlow);
  root.style.setProperty("--projector", palette.projector);
  root.style.setProperty("--bg-deep", palette.bgDeep);
  root.style.setProperty("--bg-mid", palette.bgMid);
  root.style.setProperty("--surface", palette.surface);
  root.style.setProperty("--surface-2", palette.surface2);
  root.dataset.posterTheme = "1";
}

export function clearPosterPalette(): void {
  const root = document.documentElement;
  for (const key of PALETTE_VARS) {
    root.style.removeProperty(key);
  }
  delete root.dataset.posterTheme;
}
