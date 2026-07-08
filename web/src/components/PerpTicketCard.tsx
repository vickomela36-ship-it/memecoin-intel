"use client";

import { useState } from "react";
import { cx, fmtPrice } from "@/lib/utils";
import { getChallenge } from "@/lib/storage";
import type { PerpTicket } from "@/types";

const DIR_COLOR: Record<PerpTicket["direction"], string> = {
  LONG: "var(--signal-long)",
  SHORT: "var(--signal-short)",
  "STAND ASIDE": "var(--text-secondary)",
};

/** Risk 5% of bankroll per perp trade. */
const RISK_FRACTION = 0.05;

function fundingCountdown(nextMs: number): string {
  const diff = nextMs - Date.now();
  if (diff <= 0) return "now";
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function PerpTicketCard({ ticket }: { ticket: PerpTicket }) {
  const [open, setOpen] = useState(false);
  const clr = DIR_COLOR[ticket.direction];
  const actionable = ticket.direction !== "STAND ASIDE";

  const ch = getChallenge();
  const bankroll = ch.active ? ch.currentBankroll : 100;
  const riskUsd = bankroll * RISK_FRACTION;
  const positionUsd = riskUsd / (ticket.stopPct / 100);
  const marginUsd = positionUsd / ticket.maxLev;
  const fundingCostUsd = positionUsd * (Math.abs(ticket.fundingPct8h) / 100);
  const liqDistPct = (100 / ticket.maxLev) * 0.9;

  return (
    <div className={cx("card", actionable && ticket.confidence !== "LOW" && "edge-glow")}>
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="font-mono-display text-lg">{ticket.display}</span>
          <span className="font-mono-display text-sm text-[var(--text-secondary)]">
            {fmtPrice(ticket.markPrice)}
          </span>
          <span
            className="font-mono-display text-xs"
            style={{ color: ticket.change24h >= 0 ? "var(--signal-long)" : "var(--signal-short)" }}
          >
            {ticket.change24h >= 0 ? "▲" : "▼"} {ticket.change24h.toFixed(1)}% 24h
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="font-mono-display text-sm px-3 py-1 rounded-input"
            style={{ color: clr, border: `1px solid ${clr}`, background: `${clr}15` }}
          >
            {ticket.direction}
          </span>
          <span className="font-mono-display text-xs text-[var(--text-secondary)]">
            bias {ticket.bias >= 0 ? "+" : ""}{ticket.bias} · {ticket.confidence}
          </span>
        </div>
      </div>

      {/* Regime line */}
      <div className="text-sm text-[var(--text-secondary)] mt-1">{ticket.regime}</div>
      {ticket.squeezeWatch && (
        <div
          className="mt-1 text-sm font-mono-display pulse-live"
          style={{ color: "var(--signal-edge)" }}
        >
          ⚡ {ticket.squeezeWatch}
        </div>
      )}

      {/* Trade ticket */}
      {actionable ? (
        <div
          className="mt-3 px-3 py-2 rounded-input font-mono-display text-sm space-y-1"
          style={{ background: "var(--bg-elevated)", borderLeft: `3px solid ${clr}` }}
        >
          <div>
            <span className="text-[var(--text-secondary)]">TICKET</span>{" "}
            {ticket.direction} @ {fmtPrice(ticket.entry)}{" "}
            <span className="text-[var(--text-tertiary)]">
              (better: pullback to {fmtPrice(ticket.pullbackEntry)})
            </span>
          </div>
          <div>
            Stop {fmtPrice(ticket.stopPrice)} (-{ticket.stopPct}%) · TP1{" "}
            {fmtPrice(ticket.tp1)} (1.5R) · TP2 {fmtPrice(ticket.tp2)} (3R)
          </div>
          <div style={{ color: clr }}>
            Size: ${positionUsd.toFixed(0)} position = ${marginUsd.toFixed(2)}{" "}
            margin × {ticket.maxLev}x · risking ${riskUsd.toFixed(2)} (
            {(RISK_FRACTION * 100).toFixed(0)}% of ${bankroll.toFixed(0)})
          </div>
          <div className="text-xs text-[var(--text-tertiary)]">
            Liq ≈ {liqDistPct.toFixed(1)}% away at {ticket.maxLev}x — {(liqDistPct / ticket.stopPct).toFixed(1)}x
            beyond your stop. Never raise leverage past this.
          </div>
        </div>
      ) : (
        <div className="mt-3 px-3 py-2 rounded-input text-sm text-[var(--text-secondary)]"
          style={{ background: "var(--bg-elevated)" }}>
          No edge — signals conflict. Standing aside is a position.
        </div>
      )}

      {/* Whale prints */}
      {ticket.whale && ticket.whale.count > 0 && (
        <div
          className="mt-2 px-3 py-1.5 rounded-input text-xs font-mono-display"
          style={{
            background: "var(--bg-elevated)",
            borderLeft: `3px solid ${
              ticket.whale.netUsd >= 0 ? "var(--signal-long)" : "var(--signal-short)"
            }`,
          }}
        >
          <span className="text-[var(--text-secondary)]">
            WHALE PRINTS ({ticket.whale.count} trades ≥ $
            {(ticket.whale.thresholdUsd / 1000).toFixed(0)}K, last ~
            {ticket.whale.windowMin}m):
          </span>{" "}
          <span style={{ color: "var(--signal-long)" }}>
            buys ${(ticket.whale.buyUsd / 1e6).toFixed(2)}M
          </span>{" "}
          ·{" "}
          <span style={{ color: "var(--signal-short)" }}>
            sells ${(ticket.whale.sellUsd / 1e6).toFixed(2)}M
          </span>{" "}
          ·{" "}
          <span
            style={{
              color:
                ticket.whale.netUsd >= 0
                  ? "var(--signal-long)"
                  : "var(--signal-short)",
            }}
          >
            net {ticket.whale.netUsd >= 0 ? "+" : "-"}$
            {(Math.abs(ticket.whale.netUsd) / 1e6).toFixed(2)}M
          </span>{" "}
          · largest ${(ticket.whale.largestUsd / 1e6).toFixed(2)}M
        </div>
      )}

      {/* Funding line */}
      <div className="flex items-center justify-between mt-2 text-xs font-mono-display flex-wrap gap-1">
        <span className="text-[var(--text-secondary)]">
          Funding {ticket.fundingPct8h >= 0 ? "+" : ""}
          {ticket.fundingPct8h}%/8h · next in {fundingCountdown(ticket.nextFundingMs)} ·
          ~${fundingCostUsd.toFixed(2)} per 8h at this size
        </span>
        <span className="text-[var(--text-tertiary)]">
          ATR {ticket.atrPct}% · OI 24h {ticket.oiChange24hPct >= 0 ? "+" : ""}
          {ticket.oiChange24hPct}%
        </span>
      </div>

      {/* Breakdown */}
      <button
        onClick={() => setOpen(!open)}
        className="mt-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display"
      >
        {open ? "▾" : "▸"} Why this bias
      </button>
      {open && (
        <table className="data-table mt-2">
          <thead>
            <tr><th>Signal</th><th>Weight</th><th>Score</th><th>Detail</th></tr>
          </thead>
          <tbody>
            {ticket.components.map((c) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td className="font-mono-display">{c.weightPct}%</td>
                <td
                  className="font-mono-display"
                  style={{
                    color: c.score > 15 ? "var(--signal-long)" : c.score < -15 ? "var(--signal-short)" : "var(--text-tertiary)",
                  }}
                >
                  {c.score >= 0 ? "+" : ""}{Math.round(c.score)}
                </td>
                <td className="text-[var(--text-secondary)]">{c.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {ticket.warnings.length > 0 && (
        <div className="mt-2 text-xs" style={{ color: "var(--signal-neutral)" }}>
          ⚠ {ticket.warnings.join(" · ")}
        </div>
      )}

      {/* Execution link + disclaimer */}
      <div className="flex items-center justify-between mt-2 flex-wrap gap-2">
        <a
          href={
            ticket.source === "Bybit"
              ? `https://www.bybit.com/trade/usdt/${ticket.symbol}`
              : `https://www.binance.com/en/futures/${ticket.symbol}`
          }
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-mono-display text-[var(--signal-edge)] hover:underline"
        >
          Open {ticket.symbol} on {ticket.source} ↗
        </a>
        <span className="text-xs text-[var(--text-tertiary)]">
          Leverage amplifies losses. Not financial advice.
        </span>
      </div>
    </div>
  );
}
