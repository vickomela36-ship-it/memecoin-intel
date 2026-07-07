"use client";

import { useState } from "react";
import { cx } from "@/lib/utils";
import type { MatchEdge } from "@/types";

const TIER_COLOR: Record<string, string> = {
  STRONG: "var(--signal-edge)",
  LEAN: "var(--signal-neutral)",
  PASS: "var(--text-tertiary)",
};

export default function MatchCard({ match }: { match: MatchEdge }) {
  const [open, setOpen] = useState(false);
  const kickoff = new Date(match.kickoff);

  return (
    <div className={cx("card", match.hasStrong && "edge-glow")}>
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          {match.hasStrong && (
            <span
              className="font-mono-display text-xs px-2 py-0.5 rounded-input pulse-live"
              style={{
                color: "var(--signal-edge)",
                border: "1px solid var(--signal-edge)",
                background: "var(--accent-glow)",
              }}
            >
              STRONG CALL
            </span>
          )}
          <span className="font-mono-display">
            {match.home} <span className="text-[var(--text-tertiary)]">vs</span>{" "}
            {match.away}
          </span>
        </div>
        <span className="text-xs text-[var(--text-secondary)] font-mono-display">
          {match.competition} ·{" "}
          {kickoff.toLocaleString(undefined, {
            weekday: "short",
            hour: "2-digit",
            minute: "2-digit",
            month: "short",
            day: "numeric",
          })}
        </span>
      </div>

      {/* Binary questions */}
      <table className="data-table mt-3">
        <thead>
          <tr>
            <th>Market</th>
            <th>Fair value</th>
            <th>Buy YES below</th>
            <th>Buy NO above</th>
            <th>Kelly @ YES</th>
            <th>Call</th>
          </tr>
        </thead>
        <tbody>
          {match.questions.map((q) => (
            <tr key={q.key}>
              <td className="font-mono-display text-xs">{q.question}</td>
              <td className="font-mono-display">
                {(q.fairProb * 100).toFixed(0)}¢
              </td>
              <td
                className="font-mono-display"
                style={{ color: "var(--signal-long)" }}
              >
                &lt; {q.buyYesBelow}¢
              </td>
              <td
                className="font-mono-display"
                style={{ color: "var(--signal-short)" }}
              >
                &gt; {q.buyNoAbove}¢
              </td>
              <td className="font-mono-display text-[var(--text-secondary)]">
                {q.kellyYesPct > 0 ? `${q.kellyYesPct}%` : "—"}
              </td>
              <td
                className="font-mono-display text-xs"
                style={{ color: TIER_COLOR[q.tier] }}
              >
                {q.tier}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="text-xs text-[var(--text-tertiary)] mt-2">
        How to use: if the platform&apos;s YES price is below &quot;buy YES
        below&quot;, YES is underpriced — and vice-versa for NO. Between the two
        numbers there is no edge: don&apos;t bet.
      </div>

      {/* Breakdown */}
      <button
        onClick={() => setOpen(!open)}
        className="mt-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display"
      >
        {open ? "▾" : "▸"} Where the number comes from
      </button>
      {open && (
        <ul className="mt-2 text-sm space-y-0.5 text-[var(--text-secondary)]">
          {match.consensusProbs ? (
            <>
              <li>
                • De-vigged consensus of {match.booksCount} bookmakers (85%
                weight): H {(match.consensusProbs.home * 100).toFixed(0)}% / D{" "}
                {(match.consensusProbs.draw * 100).toFixed(0)}% / A{" "}
                {(match.consensusProbs.away * 100).toFixed(0)}%
              </li>
              <li>
                • ELO sanity check (15% weight): {match.home}{" "}
                {match.homeElo.toFixed(0)} vs {match.away}{" "}
                {match.awayElo.toFixed(0)} (+65 home adv)
              </li>
            </>
          ) : (
            <li style={{ color: "var(--signal-neutral)" }}>
              ⚠ No bookmaker odds found for this match — fair value is pure
              ELO, treat with less confidence (calls capped at LEAN).
            </li>
          )}
          <li className="text-[var(--text-tertiary)]">
            ⚠ Model limitation: neither books nor ELO know team news from the
            last hour. This is a pricing edge, not a certainty.
          </li>
        </ul>
      )}

      <div className="flex justify-end mt-1">
        <span className="text-xs text-[var(--text-tertiary)]">
          Not financial advice.
        </span>
      </div>
    </div>
  );
}
