"use client";

import { useState } from "react";
import { fmtPct, fmtPrice } from "@/lib/utils";
import type { CryptoScoreRow } from "@/types";
import ScoreBar from "./ScoreBar";
import Sparkline from "./Sparkline";

function scoreColor(score: number): string {
  if (score >= 60) return "var(--signal-long)";
  if (score >= 40) return "var(--signal-neutral)";
  return "var(--signal-short)";
}

export default function HeatmapGrid({ rows }: { rows: CryptoScoreRow[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
      {rows.map((r) => {
        const clr = scoreColor(r.score);
        const open = expanded === r.id;
        const arrow = r.change24h > 1 ? "↑" : r.change24h < -1 ? "↓" : "→";
        return (
          <button
            key={r.id}
            onClick={() => setExpanded(open ? null : r.id)}
            className="card text-left hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono-display text-base">{r.symbol}</span>
              <span
                className="font-mono-display text-lg tabular-nums"
                style={{ color: clr }}
              >
                {r.score} {arrow}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] mt-0.5">
              <span>{fmtPrice(r.price)}</span>
              <span style={{ color: r.change24h >= 0 ? "var(--signal-long)" : "var(--signal-short)" }}>
                {fmtPct(r.change24h)}
              </span>
            </div>
            <div className="mt-1">
              <Sparkline data={r.sparkline} />
            </div>
            <div className="mt-1">
              <ScoreBar score={r.score} color={clr} />
            </div>
            <div
              className="text-xs font-mono-display mt-1"
              style={{ color: clr }}
            >
              {r.label}
            </div>

            {open && (
              <div className="mt-2 border-t border-[var(--border-subtle)] pt-2 space-y-1">
                {r.components.map((c) => (
                  <div key={c.name} className="text-xs">
                    <div className="flex justify-between text-[var(--text-secondary)]">
                      <span>
                        {c.name}{" "}
                        <span className="text-[var(--text-tertiary)]">
                          ({c.weightPct}%)
                        </span>
                      </span>
                      <span className="font-mono-display">
                        {Math.round(c.score)}
                      </span>
                    </div>
                    <div className="text-[var(--text-tertiary)]">{c.detail}</div>
                  </div>
                ))}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
