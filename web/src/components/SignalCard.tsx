"use client";

import { useState } from "react";
import { cx, fmtPrice, fmtUsd, timeAgo } from "@/lib/utils";
import { positionPlan } from "@/lib/challenge";
import { addWatch, getChallenge } from "@/lib/storage";
import type { MemeSignal } from "@/types";
import ScoreBar from "./ScoreBar";

const MODE_COLOR: Record<MemeSignal["mode"], string> = {
  LAUNCH: "var(--signal-long)",
  RECOVERY: "var(--signal-neutral)",
  "HIGHER-CAP": "var(--signal-long)",
  DEGEN: "var(--signal-short)",
};

const TIER_COLOR: Record<string, string> = {
  "100x MOONSHOT": "var(--signal-edge)",
  "10x RUNNER": "var(--signal-long)",
  "5x POTENTIAL": "var(--signal-neutral)",
  "3x POSSIBLE": "var(--text-secondary)",
};

export default function SignalCard({
  signal,
  fetchedAt,
}: {
  signal: MemeSignal;
  fetchedAt: number;
}) {
  const [open, setOpen] = useState(false);
  const [watched, setWatched] = useState<null | "added" | "dup">(null);
  const clr = MODE_COLOR[signal.mode];
  const strong = signal.score >= 75;

  const ch = getChallenge();
  const bankroll = ch.active ? ch.currentBankroll : 100;
  const plan = positionPlan(bankroll, signal.sizingKey);

  function handleWatch() {
    const ok = addWatch({
      address: signal.address,
      symbol: signal.symbol,
      name: signal.name,
      entryPrice: signal.priceUsd,
      target2x: signal.priceUsd * 2,
      grade: signal.tier ?? signal.grade ?? signal.mode,
      pairUrl: signal.pairUrl,
    });
    setWatched(ok ? "added" : "dup");
  }

  return (
    <div className={cx("card", strong && "edge-glow")}>
      {/* Header row */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="font-mono-display text-xs px-2 py-0.5 rounded-input"
            style={{ color: clr, border: `1px solid ${clr}`, background: `${clr}15` }}
          >
            {signal.mode}
          </span>
          {signal.tier && (
            <span
              className="font-mono-display text-xs px-2 py-0.5 rounded-input"
              style={{
                color: TIER_COLOR[signal.tier] ?? "var(--text-secondary)",
                border: `1px solid ${TIER_COLOR[signal.tier] ?? "var(--text-secondary)"}`,
              }}
            >
              {signal.tier}
            </span>
          )}
          {signal.grade && (
            <span
              className="font-mono-display text-xs px-2 py-0.5 rounded-input"
              style={{
                color: signal.grade === "A" ? "var(--signal-long)" : "var(--text-secondary)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              GRADE {signal.grade}
            </span>
          )}
          {signal.riskLevel && (
            <span
              className="font-mono-display text-xs px-2 py-0.5 rounded-input"
              style={{ color: "var(--signal-short)", border: "1px solid var(--signal-short)" }}
            >
              RISK: {signal.riskLevel}
            </span>
          )}
          <span className="font-mono-display text-lg">${signal.symbol}</span>
          <span className="text-sm text-[var(--text-secondary)] hidden sm:inline">
            {signal.name.slice(0, 24)}
          </span>
        </div>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {timeAgo(fetchedAt)}
        </span>
      </div>

      {/* Score */}
      <div className="mt-2">
        <ScoreBar score={signal.score} color={clr} />
      </div>

      {/* Stat grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 mt-3 text-sm">
        <Stat label="MCap" value={fmtUsd(signal.fdv)} />
        <Stat label="Liquidity" value={fmtUsd(signal.liquidity)} />
        <Stat
          label="Vol/MCap"
          value={signal.fdv > 0 ? `${(signal.vol24h / signal.fdv).toFixed(1)}x` : "—"}
        />
        <Stat
          label="Buys/Sells"
          value={signal.buySellRatio > 0 ? `${signal.buySellRatio.toFixed(1)}x` : "—"}
        />
        <Stat label="Price" value={fmtPrice(signal.priceUsd)} />
        <Stat
          label="Age"
          value={
            signal.ageHours < 24
              ? `${signal.ageHours.toFixed(1)}h`
              : `${(signal.ageHours / 24).toFixed(0)}d`
          }
        />
        <Stat label="Vol 1h" value={fmtUsd(signal.volH1)} />
        <Stat label="Boosts" value={signal.boosts ? String(signal.boosts) : "—"} />
      </div>

      {/* Trade plan — sized from the live challenge bankroll */}
      <div
        className="mt-3 px-3 py-2 rounded-input text-sm font-mono-display"
        style={{ background: "var(--bg-elevated)", borderLeft: `3px solid ${clr}` }}
      >
        <span className="text-[var(--text-secondary)]">PLAN</span>{" "}
        Buy <b>${plan.sizeUsd.toFixed(2)}</b> ({(plan.fraction * 100).toFixed(0)}%
        of ${bankroll.toFixed(0)}) · Stop <b>-{plan.stopPct}%</b> (max loss $
        {plan.maxLossUsd.toFixed(2)}) · Sell 50% @ <b>{plan.tp1Mult}x</b> · 25% @{" "}
        <b>{plan.tp2Mult}x</b> · ride 25%
        <div className="text-xs text-[var(--text-tertiary)] mt-0.5">{plan.why}</div>
      </div>

      {/* Expandable reasoning */}
      <button
        onClick={() => setOpen(!open)}
        className="mt-3 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display"
      >
        {open ? "▾" : "▸"} Why this signal
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          <table className="data-table">
            <thead>
              <tr>
                <th>Component</th>
                <th>Weight</th>
                <th>Score</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {signal.components.map((c) => (
                <tr key={c.name}>
                  <td>{c.name}</td>
                  <td className="font-mono-display">{c.weightPct}%</td>
                  <td className="font-mono-display">{Math.round(c.score)}</td>
                  <td className="text-[var(--text-secondary)]">{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {signal.reasons.length > 0 && (
            <ul className="text-sm space-y-0.5">
              {signal.reasons.map((r) => (
                <li key={r} className="text-[var(--text-secondary)]">
                  • {r}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Risk warnings */}
      {signal.warnings.length > 0 && (
        <div className="mt-2 text-xs" style={{ color: "var(--signal-short)" }}>
          ⚠ {signal.warnings.slice(0, 2).join(" · ")}
        </div>
      )}

      {/* Actions + disclaimer */}
      <div className="flex items-center justify-between mt-2 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <button
            onClick={handleWatch}
            className="text-xs font-mono-display px-2 py-1 rounded-btn border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-active)]"
          >
            {watched === "added" ? "✓ Watching" : watched === "dup" ? "Already watching" : "+ Watch"}
          </button>
          <a
            href={`https://jup.ag/swap/SOL-${signal.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-mono-display px-2 py-1 rounded-btn"
            style={{
              color: "var(--signal-long)",
              border: "1px solid var(--signal-long)",
            }}
          >
            BUY (Jupiter) ↗
          </a>
          {signal.pairUrl && (
            <a
              href={signal.pairUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-mono-display text-[var(--signal-edge)] hover:underline"
            >
              DexScreener ↗
            </a>
          )}
        </div>
        <span className="text-xs text-[var(--text-tertiary)]">
          Not financial advice. Size accordingly.
        </span>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between sm:block">
      <span className="text-xs text-[var(--text-tertiary)] font-mono-display uppercase tracking-wide block">
        {label}
      </span>
      <span className="font-mono-display text-sm">{value}</span>
    </div>
  );
}
