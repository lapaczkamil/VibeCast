import { useEffect, useState } from "react";

const LOADING_LINES = [
  "Reading the mix",
  "Tuning into the mood",
  "Scanning the reel",
  "Matching films to the signal",
];

type RecommendLoadingProps = {
  lineIndex: number;
};

export function RecommendLoading({ lineIndex }: RecommendLoadingProps) {
  const [dots, setDots] = useState(1);
  const line = LOADING_LINES[lineIndex % LOADING_LINES.length];

  useEffect(() => {
    const id = window.setInterval(() => {
      setDots((n) => (n % 3) + 1);
    }, 420);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="recommend-loading" role="status" aria-live="polite">
      <p className="recommend-loading-line">
        {line}
        <span className="recommend-loading-ellipsis" aria-hidden="true">
          {".".repeat(dots)}
        </span>
      </p>
    </div>
  );
}

export { LOADING_LINES };
