type AlbumConveyorProps = {
  /** Album art URLs already present in session cache — no Spotify API calls. */
  imageUrls: string[];
};

type RowDirection = "left" | "right" | "left-slow";

function uniqueUrls(urls: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const url of urls) {
    if (!url || seen.has(url)) continue;
    seen.add(url);
    out.push(url);
  }
  return out;
}

/** Repeat until we have enough tiles, then duplicate once for a seamless loop. */
function buildLoop(urls: string[], minTiles = 24): string[] {
  if (urls.length === 0) return [];
  const base: string[] = [];
  while (base.length < minTiles) {
    base.push(...urls);
  }
  return [...base, ...base];
}

function rotate(urls: string[], offset: number): string[] {
  if (urls.length === 0) return urls;
  const n = offset % urls.length;
  return [...urls.slice(n), ...urls.slice(0, n)];
}

function ConveyorRow({
  urls,
  direction,
}: {
  urls: string[];
  direction: RowDirection;
}) {
  return (
    <div
      className={`album-conveyor-row album-conveyor-row--${direction}`}
    >
      <div className="album-conveyor-track">
        {urls.map((url, index) => (
          <img
            key={`${direction}-${index}-${url}`}
            className="album-conveyor-art"
            src={url}
            alt=""
            width={160}
            height={160}
            loading="lazy"
            decoding="async"
            draggable={false}
          />
        ))}
      </div>
    </div>
  );
}

export function AlbumConveyor({ imageUrls }: AlbumConveyorProps) {
  const unique = uniqueUrls(imageUrls);
  if (unique.length < 2) return null;
  const loop = buildLoop(unique, Math.max(24, unique.length * 2));

  return (
    <div className="album-conveyor" aria-hidden="true">
      <ConveyorRow urls={loop} direction="left" />
      <ConveyorRow urls={rotate(loop, 7)} direction="right" />
      <ConveyorRow urls={rotate(loop, 13)} direction="left-slow" />
    </div>
  );
}
