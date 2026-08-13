"use client";

import { fmtPrice } from "@/lib/utils";
import type { ChartInfo } from "@/types";

const TREND_COLOR: Record<string, string> = {
  UPTREND: "var(--signal-long)",
  DOWNTREND: "var(--signal-short)",
  RANGING: "var(--signal-neutral)",
  "REVERSAL FORMING": "var(--signal-edge)",
};

const GRADE_COLOR: Record<string, string> = {
  "high-confidence zone": "var(--signal-long)",
  "tradable area": "var(--signal-neutral)",
  "possible reaction": "var(--text-secondary)",
  none: "var(--text-tertiary)",
};

/**
 * Market-structure read for a single token. Trend state, body-to-body fib,
 * price-zone confluence and an auto-invalidation level — every number is
 * shown, and the memecoin caveats (wick overshoot, age gate) are surfaced
 * rather than hidden. Surfaces structure; never says buy or sell.
 */
export default function ChartCard({ chart }: { chart: ChartInfo }) {
  const clr = TREND_COLOR[chart.structure.state] ?? "var(--text-secondary)";

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="font-display text-base font-semibold">MARKET STRUCTURE</h3>
        <span
          className="font-mono-display text-xs px-2 py-0.5 rounded-input"
          style={{ color: clr, border: `1px solid ${clr}`, background: `${clr}15` }}
        >
          {chart.structure.state}
        </span>
      </div>
      <p className="text-xs text-[var(--text-secondary)]">{chart.structure.detail}.</p>

      {/* Age / history gate — honest suppression */}
      {!chart.usable && chart.suppressReason && (
        <div className="text-xs rounded-input px-3 py-2" style={{ background: "var(--bg-elevated)", color: "var(--signal-neutral)" }}>
          {chart.suppressReason}
        </div>
      )}

      {/* Fibonacci retracement */}
      {chart.usable && chart.fib && (
        chart.fib.drawn ? (
          <div>
            <div className="flex items-center justify-between">
              <span className="font-mono-display text-sm text-[var(--text-secondary)]">
                FIB RETRACEMENT{" "}
                <span className="text-[var(--text-tertiary)]">
                  ({fmtPrice(chart.fib.low)} → {fmtPrice(chart.fib.high)})
                </span>
              </span>
              {chart.fib.inGoldenPocket && (
                <span className="font-mono-display text-xs pulse-live" style={{ color: "var(--signal-edge)" }}>
                  ● price in golden pocket
                </span>
              )}
            </div>
            <table className="data-table mt-1">
              <thead>
                <tr><th>Level</th><th>Price</th><th>Note</th></tr>
              </thead>
              <tbody>
                {chart.fib.levels.map((l) => (
                  <tr key={l.ratio}>
                    <td className="font-mono-display" style={{ color: l.golden ? "var(--signal-edge)" : undefined }}>
                      {(l.ratio * 100).toFixed(1)}%
                    </td>
                    <td className="font-mono-display">{fmtPrice(l.price)}</td>
                    <td className="text-[var(--text-secondary)]">
                      {l.golden ? "0.618 golden level — the highest-probability reaction zone" : l.ratio === 0.786 ? "last line of the retracement" : "shallow retrace"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-[var(--text-tertiary)] mt-1">{chart.fib.reason}</p>
          </div>
        ) : (
          <div className="text-xs text-[var(--text-tertiary)]">{chart.fib.reason}</div>
        )
      )}

      {/* Confluence counter */}
      {chart.usable && chart.confluence && chart.confluence.count > 0 && (
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono-display text-sm text-[var(--text-secondary)]">CONFLUENCE</span>
            <span
              className="font-mono-display text-xs px-2 py-0.5 rounded-input"
              style={{ color: GRADE_COLOR[chart.confluence.grade], border: `1px solid ${GRADE_COLOR[chart.confluence.grade]}` }}
            >
              {chart.confluence.count} signal{chart.confluence.count > 1 ? "s" : ""} · {chart.confluence.grade}
            </span>
          </div>
          <ul className="text-xs mt-1 space-y-0.5">
            {chart.confluence.signals.map((s, i) => (
              <li key={i} className="text-[var(--text-secondary)]">
                • <span className="text-[var(--text-primary)]">{s.kind}</span> @ {fmtPrice(s.price)} — {s.detail}
              </li>
            ))}
          </ul>
          <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
            Independent signals stacking at one price = a stronger reaction zone. 1 = possible, 2 = tradable, 3+ = high-confidence.
          </p>
        </div>
      )}

      {/* Invalidation */}
      {chart.usable && chart.invalidation && chart.invalidation.level !== null && (
        <div className="rounded-input px-3 py-2" style={{ background: "var(--bg-elevated)", borderLeft: "3px solid var(--signal-short)" }}>
          <div className="font-mono-display text-sm">
            <span className="text-[var(--text-secondary)]">INVALIDATION</span>{" "}
            <b style={{ color: "var(--signal-short)" }}>{fmtPrice(chart.invalidation.level)}</b>
            {chart.invalidation.confirmed && (
              <span className="ml-2 text-xs" style={{ color: "var(--signal-short)" }}>● confirmed broken</span>
            )}
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            The setup dies on {chart.invalidation.basis}. {chart.invalidation.note}
          </p>
        </div>
      )}

      <p className="text-xs text-[var(--text-tertiary)] border-t border-[var(--border-subtle)] pt-2">
        Structure describes where price is — it is not a call to buy or sell. An
        uptrend is generally a better entry than a &quot;cheap&quot; downtrend, but
        levels only matter once price has reacted to them repeatedly.
      </p>
    </div>
  );
}
