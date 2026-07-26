"use client";

import { useMemo, useState } from "react";
import { computeSentiment, type SentimentInput } from "@/lib/sentiment";

function scoreColor(s: number): string {
  if (s >= 30) return "var(--signal-long)";
  if (s <= -30) return "var(--signal-short)";
  return "var(--signal-neutral)";
}

/**
 * One consistent sentiment component. Score + confidence band, a
 * velocity/acceleration read, a prominent divergence flag, and a
 * click-to-expand components breakdown so nothing is a black box.
 */
export default function Sentiment({ input }: { input: SentimentInput }) {
  const [open, setOpen] = useState(false);
  // Recompute only when the underlying inputs change (not every render)
  const sig = useMemo(
    () => computeSentiment(input),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [input.address, input.buySellRatio, input.volH1, input.vol24h, input.txns1h, input.h1]
  );
  const clr = scoreColor(sig.score);
  const velArrow = sig.velocity > 2 ? "▲" : sig.velocity < -2 ? "▼" : "→";
  const accelSignal =
    sig.acceleration > 3 ? "accelerating" : sig.acceleration < -3 ? "fading" : "steady";
  const lowConf = sig.confidence < 0.45;

  // Signature divergence bar geometry — sentiment fills from the left, price
  // from the right; each capped at half the track so the two reads face off.
  const sentW = Math.min(50, Math.abs(sig.score) / 2);
  const priceW = Math.min(50, Math.abs(input.h1) * 3);
  const diverging = sig.divergence !== "none";

  return (
    <div
      className="mt-2 px-3 py-2 rounded-input text-sm"
      style={{ background: "var(--bg-elevated)", borderLeft: `3px solid ${clr}` }}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-mono-display flex items-center gap-2">
          <span
            className="signal-fire"
            style={{ ["--fire-color" as string]: clr }}
            aria-hidden
          />
          <span className="text-[var(--text-secondary)]">SENTIMENT</span>{" "}
          <b style={{ color: clr }} className="tabular">
            {sig.score >= 0 ? "+" : ""}
            {sig.score}
          </b>{" "}
          <span style={{ color: clr }}>
            {velArrow} {accelSignal}
          </span>
        </span>
        {/* Confidence band */}
        <span className="flex items-center gap-1.5 text-xs font-mono-display text-[var(--text-tertiary)]">
          conf
          <span className="inline-block w-12 h-1.5 rounded-sm bg-[var(--bg-primary)] overflow-hidden align-middle">
            <span
              className="block h-full"
              style={{
                width: `${Math.round(sig.confidence * 100)}%`,
                background: lowConf ? "var(--signal-short)" : "var(--signal-long)",
              }}
            />
          </span>
          {Math.round(sig.confidence * 100)}%
        </span>
      </div>

      {/* Signature divergence bar — sentiment (left) vs price (right) */}
      <div
        className={`divergence-bar mt-2${diverging ? " dv-active" : ""}`}
        role="img"
        aria-label={`sentiment magnitude ${Math.abs(sig.score)}, price move ${input.h1.toFixed(1)}%`}
      >
        <span className="dv-sent" style={{ width: `${sentW}%` }} />
        <span
          className="dv-price"
          style={{
            width: `${priceW}%`,
            background: input.h1 >= 0 ? "var(--signal-long)" : "var(--signal-short)",
            opacity: 0.55,
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] font-mono-display text-[var(--text-tertiary)] mt-0.5">
        <span>flow</span>
        <span>price {input.h1 >= 0 ? "+" : ""}{input.h1.toFixed(1)}%</span>
      </div>

      {lowConf && (
        <div className="text-xs mt-0.5" style={{ color: "var(--signal-neutral)" }}>
          Thin sample ({input.txns1h} txns) — this score is low-confidence, treat it loosely.
        </div>
      )}

      {sig.divergence !== "none" && (
        <div
          className="text-xs mt-1 font-mono-display pulse-live"
          style={{ color: sig.divergence === "bullish" ? "var(--signal-long)" : "var(--signal-short)" }}
        >
          ⚠ {sig.divergence.toUpperCase()} DIVERGENCE — {sig.divergenceNote}
        </div>
      )}

      <button
        onClick={() => setOpen(!open)}
        className="mt-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display"
      >
        {open ? "▾" : "▸"} what drives this
      </button>
      {open && (
        <table className="data-table mt-1">
          <thead>
            <tr><th>Component</th><th>Value</th><th>Weight</th><th>Source</th></tr>
          </thead>
          <tbody>
            {sig.components.map((c) => (
              <tr key={c.label}>
                <td>{c.label}</td>
                <td className="font-mono-display">{c.value}</td>
                <td className="font-mono-display">{Math.round(c.weight * 100)}%</td>
                <td className="text-[var(--text-secondary)] text-xs">{c.source}</td>
              </tr>
            ))}
          </tbody>
          <tbody>
            <tr>
              <td className="text-[var(--text-tertiary)] text-xs" colSpan={4}>
                Velocity {sig.velocity >= 0 ? "+" : ""}{sig.velocity} · acceleration{" "}
                {sig.acceleration >= 0 ? "+" : ""}{sig.acceleration} · price NOT a
                component (that&apos;s what divergence compares against).
              </td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}
