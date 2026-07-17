import { useEffect, useState, type CSSProperties } from "react";

type AudioMetersProps = {
  /** Stronger pulse while Spotify is actively playing. */
  active?: boolean;
};

type MeterPhase = "ambient" | "live" | "coasting";

const COAST_MS = 3800;

/** Tall subtle EQ bars for page background only — full viewport width. */
const BARS = [
  0.22, 0.38, 0.55, 0.32, 0.7, 0.45, 0.88, 0.28, 0.6, 0.48, 0.78, 0.35, 0.92,
  0.4, 0.65, 0.3, 0.52, 0.82, 0.36, 0.68, 0.5, 0.9, 0.42, 0.58, 0.75, 0.33,
  0.62, 0.44, 0.85, 0.27, 0.72, 0.5, 0.38, 0.66, 0.8, 0.34, 0.56, 0.46, 0.94,
  0.29, 0.64, 0.41, 0.77, 0.53, 0.31, 0.69, 0.47, 0.86,
];

export function AudioMeters({ active = false }: AudioMetersProps) {
  const [phase, setPhase] = useState<MeterPhase>(active ? "live" : "ambient");

  useEffect(() => {
    if (active) {
      setPhase("live");
      return;
    }
    setPhase((current) => (current === "live" ? "coasting" : "ambient"));
  }, [active]);

  useEffect(() => {
    if (phase !== "coasting") return;
    const id = window.setTimeout(() => setPhase("ambient"), COAST_MS);
    return () => window.clearTimeout(id);
  }, [phase]);

  const phaseClass =
    phase === "live"
      ? " audio-meters-bg--live"
      : phase === "coasting"
        ? " audio-meters-bg--coasting"
        : " audio-meters-bg--ambient";

  return (
    <div
      className={`audio-meters-bg${phaseClass}`}
      aria-hidden="true"
    >
      {BARS.map((level, index) => (
        <span
          key={index}
          className="audio-meters-bg-bar"
          style={
            {
              "--bar-base": String(level),
              "--bar-delay": `${index * 0.12}s`,
              "--bar-duration": `${2.4 + (index % 6) * 0.45}s`,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
