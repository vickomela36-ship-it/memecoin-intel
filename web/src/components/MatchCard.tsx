"use client";

import { useState } from "react";
import { cx } from "@/lib/utils";
import type { MatchEdge } from "@/types";

const OUTCOME_LABEL: Record<string, string> = {
  home: "Home",
  draw: "Draw",
  away: "Away",
};

export default function MatchCard({ match }: { match: MatchEdge }) {
  const [open, setOpen] = useState(false);
  const hasEdge = match.bestEdge !== null;
  const kickoff = new Date(match.kickoff);

  return (
    <div className={cx("card", hasEdge && "edge-glow")}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          {hasEdge && (
            <span
              className="font-mono-display text-xs px-2 py-0.5 rounded-input pulse-live"
              style={{
                color: "var(--signal-edge)",
                border: "1px solid var(--signal-edge)",
                background: "var(--accent-glow)",
              }}
            >
              EDGE {(match.bestEdge!.edge * 100).toFixed(1)}%
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

      {/* Model vs Market table */}
      <table className="data-table mt-3">
        <thead>
          <tr>
            <th>Outcome</th>
            <th>Model</th>
            <th>Market</th>
            <th>Edge</th>
            <th>Best odds</th>
          </tr>
        </thead>
        <tbody>
          {match.edges.map((e) => {
            const isValue = e.signal !== "NONE";
            return (
              <tr key={e.outcome}>
                <td>{OUTCOME_LABEL[e.outcome]}</td>
                <td className="font-mono-display">
                  {(e.modelProb * 100).toFixed(1)}%
                </td>
                <td className="font-mono-display">
                  {(e.impliedProb * 100).toFixed(1)}%
                </td>
                <td
                  className="font-mono-display"
                  style={{
                    color: isValue
                      ? "var(--signal-edge)"
                      : e.edge > 0
                        ? "var(--text-secondary)"
                        : "var(--text-tertiary)",
                  }}
                >
                  {e.edge >= 0 ? "+" : ""}
                  {(e.edge * 100).toFixed(1)}%{isValue ? " ◀ VALUE" : ""}
                </td>
                <td className="font-mono-display text-[var(--text-secondary)]">
                  {e.bestOdds.toFixed(2)}{" "}
                  <span className="text-[var(--text-tertiary)]">
                    ({e.bestBook})
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {hasEdge && (
        <div className="mt-2 text-sm font-mono-display">
          Kelly stake:{" "}
          <span style={{ color: "var(--signal-edge)" }}>
            {(match.bestEdge!.kellyFraction * 100).toFixed(1)}% of bankroll
          </span>{" "}
          on {OUTCOME_LABEL[match.bestEdge!.outcome]} @{" "}
          {match.bestEdge!.bestOdds.toFixed(2)}
        </div>
      )}

      <button
        onClick={() => setOpen(!open)}
        className="mt-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display"
      >
        {open ? "▾" : "▸"} Why {hasEdge ? "this edge" : "no edge"}
      </button>
      {open && (
        <ul className="mt-2 text-sm space-y-0.5 text-[var(--text-secondary)]">
          <li>
            • {match.home} ELO: {match.homeElo.toFixed(0)} (+65 home advantage
            applied)
          </li>
          <li>
            • {match.away} ELO: {match.awayElo.toFixed(0)}
          </li>
          <li>
            • Model probabilities: H {(match.probs.home * 100).toFixed(0)}% / D{" "}
            {(match.probs.draw * 100).toFixed(0)}% / A{" "}
            {(match.probs.away * 100).toFixed(0)}%
          </li>
          <li className="text-[var(--text-tertiary)]">
            ⚠ Model limitation: ELO doesn&apos;t capture tactics, injuries, or
            individual form. This is a statistical edge, not a certainty.
          </li>
        </ul>
      )}
    </div>
  );
}
