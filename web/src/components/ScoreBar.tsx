"use client";

/** Horizontal 0-100 score bar with terminal-style blocks. */
export default function ScoreBar({
  score,
  color,
}: {
  score: number;
  color?: string;
}) {
  const clr =
    color ??
    (score >= 60
      ? "var(--signal-long)"
      : score >= 40
        ? "var(--signal-neutral)"
        : "var(--signal-short)");
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-sm bg-[var(--bg-elevated)] overflow-hidden">
        <div
          className="h-full transition-all duration-500"
          style={{ width: `${Math.max(2, Math.min(100, score))}%`, background: clr }}
        />
      </div>
      <span
        className="font-mono-display text-sm tabular-nums w-8 text-right"
        style={{ color: clr }}
      >
        {Math.round(score)}
      </span>
    </div>
  );
}
