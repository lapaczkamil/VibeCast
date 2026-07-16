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

function relativeLuminance({ r, g, b }: Rgb): number {
  const lin = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lin[0]! + 0.7152 * lin[1]! + 0.0722 * lin[2]!;
}

function saturation({ r, g, b }: Rgb): number {
  const max = Math.max(r, g, b) / 255;
  const min = Math.min(r, g, b) / 255;
  if (max === min) return 0;
  const l = (max + min) / 2;
  return l > 0.5 ? (max - min) / (2 - max - min) : (max - min) / (max + min);
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

/** Pick a vivid accent from a poster image (CORS-enabled URL). */
export async function extractPosterPalette(
  imageUrl: string,
): Promise<PosterPalette> {
  const img = await loadImage(imageUrl);
  const size = 48;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas unsupported");

  ctx.drawImage(img, 0, 0, size, size);
  const { data } = ctx.getImageData(0, 0, size, size);

  let best: Rgb | null = null;
  let bestScore = -1;
  let sum: Rgb = { r: 0, g: 0, b: 0 };
  let count = 0;

  for (let i = 0; i < data.length; i += 16) {
    const r = data[i]!;
    const g = data[i + 1]!;
    const b = data[i + 2]!;
    const a = data[i + 3]!;
    if (a < 200) continue;

    const color = { r, g, b };
    const lum = relativeLuminance(color);
    if (lum < 0.06 || lum > 0.92) continue;

    const sat = saturation(color);
    const score = sat * 1.35 + (1 - Math.abs(lum - 0.42)) * 0.45;
    if (score > bestScore) {
      bestScore = score;
      best = color;
    }

    sum = { r: sum.r + r, g: sum.g + g, b: sum.b + b };
    count += 1;
  }

  const base =
    best ??
    (count > 0
      ? { r: sum.r / count, g: sum.g / count, b: sum.b / count }
      : { r: 29, g: 185, b: 84 });

  // Boost saturation slightly so UI accents stay punchy.
  const white = { r: 255, g: 255, b: 255 };
  const black = { r: 0, g: 0, b: 0 };
  const accentRgb = mix(base, white, 0.08);
  const accentHot = mix(accentRgb, white, 0.22);
  const accentWarm = mix(accentRgb, black, 0.22);
  const textBase =
    relativeLuminance(accentRgb) < 0.45
      ? mix(accentRgb, white, 0.35)
      : mix(accentRgb, black, 0.15);

  const accent = rgbToHex(accentRgb);
  const r = Math.round(accentRgb.r);
  const g = Math.round(accentRgb.g);
  const b = Math.round(accentRgb.b);

  const bgDeep = rgbToHex(mix({ r: 18, g: 18, b: 18 }, accentRgb, 0.14));
  const bgMid = rgbToHex(mix({ r: 24, g: 24, b: 24 }, accentRgb, 0.16));
  const surface = rgbToHex(mix({ r: 24, g: 24, b: 24 }, accentRgb, 0.12));
  const surface2 = rgbToHex(mix({ r: 40, g: 40, b: 40 }, accentRgb, 0.14));

  return {
    accent,
    accentHot: rgbToHex(accentHot),
    accentWarm: rgbToHex(accentWarm),
    accentText: rgbToHex(textBase),
    accentGlow: `rgba(${r}, ${g}, ${b}, 0.38)`,
    projector: `rgba(${r}, ${g}, ${b}, 0.2)`,
    bgDeep,
    bgMid,
    surface,
    surface2,
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
