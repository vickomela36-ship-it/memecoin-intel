"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getChallenge,
  getWatchlist,
  removeWatch,
  updateWatchPeaks,
  type WatchItem,
} from "@/lib/storage";
import { bestSolanaPair, fetchPairsBatch } from "@/modules/memecoin/fetchers";
import { fmtPrice, timeAgo } from "@/lib/utils";

interface LivePrice {
  price: number;
  h24: number;
}

/** "2h 14m", "3d 5h" — duration between two timestamps. */
function fmtDuration(fromMs: number, toMs: number): string {
  const s = Math.max(0, (toMs - fromMs) / 1000);
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`;
}

export default function PortfolioView() {
  const [watchlist, setWatchlist] = useState<WatchItem[]>(() => getWatchlist());
  const [live, setLive] = useState<Map<string, LivePrice>>(new Map());
  const [refreshing, setRefreshing] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);
  const refreshingRef = useRef(false);

  const challenge = getChallenge();
  const trades = challenge.trades;
  const wins = trades.filter((t) => t.pnl > 0).length;
  const totalPnl = trades.reduce((a, t) => a + t.pnl, 0);

  const refreshPrices = useCallback(async () => {
    const list = getWatchlist();
    if (!list.length || refreshingRef.current) return;
    refreshingRef.current = true;
    setRefreshing(true);
    try {
      const map = await fetchPairsBatch(list.map((w) => w.address));
      const next = new Map<string, LivePrice>();
      const priceOnly = new Map<string, number>();
      map.forEach((pairs, addr) => {
        const best = bestSolanaPair(pairs);
        if (!best) return;
        const price = Number(best.priceUsd) || 0;
        const h24 = Number(best.priceChange?.h24) || 0;
        if (price > 0) {
          next.set(addr, { price, h24 });
          priceOnly.set(addr, price);
        }
      });
      setLive(next);
      // Record any new peak-multiples permanently
      setWatchlist(updateWatchPeaks(priceOnly));
      setRefreshedAt(Date.now());
    } finally {
      refreshingRef.current = false;
      setRefreshing(false);
    }
  }, []);

  // Auto-refresh on mount and every 60s while this tab is open —
  // more observations = better peak capture.
  useEffect(() => {
    refreshPrices();
    const id = setInterval(refreshPrices, 60_000);
    return () => clearInterval(id);
  }, [refreshPrices]);

  function handleRemove(address: string) {
    removeWatch(address);
    setWatchlist(getWatchlist());
  }

  return (
    <div className="space-y-3">
      {/* ── Watchlist ─────────────────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
          <h3 className="font-mono-display text-base">
            WATCHLIST ({watchlist.length})
          </h3>
          <div className="flex items-center gap-3">
            {refreshedAt && (
              <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
                prices {timeAgo(refreshedAt)}
              </span>
            )}
            <button
              onClick={refreshPrices}
              disabled={refreshing || !watchlist.length}
              className="text-xs font-mono-display px-3 py-1.5 rounded-btn border border-[var(--border-active)] text-[var(--signal-edge)] hover:bg-[var(--accent-glow)] disabled:opacity-40"
            >
              {refreshing ? "REFRESHING…" : "REFRESH PRICES"}
            </button>
          </div>
        </div>

        {watchlist.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">
            Empty. Hit <span className="font-mono-display">+ Watch</span> on any
            signal card in the Memecoins tab.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Token</th><th>Tier</th><th>Entry</th><th>Current</th>
                  <th>PnL</th><th>Peak hit</th><th>Time to peak</th><th>→ 2x</th><th></th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map((w) => {
                  const lp = live.get(w.address);
                  const cur = lp?.price ?? null;
                  const chg = cur !== null && w.entryPrice > 0
                    ? (cur / w.entryPrice - 1) * 100
                    : null;
                  const prog = cur !== null && w.target2x > 0
                    ? Math.min(100, (cur / w.target2x) * 100)
                    : null;
                  const peak = w.peakMultiple ?? null;
                  const peakPct = peak !== null ? (peak - 1) * 100 : null;
                  return (
                    <tr key={w.address}>
                      <td>
                        {w.pairUrl ? (
                          <a
                            href={w.pairUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-mono-display text-[var(--signal-edge)] hover:underline"
                          >
                            {w.symbol}
                          </a>
                        ) : (
                          <span className="font-mono-display">{w.symbol}</span>
                        )}
                      </td>
                      <td className="text-[var(--text-secondary)] text-xs">{w.grade}</td>
                      <td className="font-mono-display">{fmtPrice(w.entryPrice)}</td>
                      <td className="font-mono-display">
                        {cur !== null ? fmtPrice(cur) : "—"}
                      </td>
                      <td
                        className="font-mono-display"
                        style={{
                          color: chg === null ? "var(--text-tertiary)"
                            : chg >= 0 ? "var(--signal-long)" : "var(--signal-short)",
                        }}
                      >
                        {chg !== null ? `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%` : "—"}
                      </td>
                      <td
                        className="font-mono-display"
                        style={{
                          color:
                            peak !== null && peak >= 2
                              ? "var(--signal-edge)"
                              : peak !== null && peak > 1.05
                                ? "var(--signal-long)"
                                : "var(--text-tertiary)",
                        }}
                      >
                        {peak !== null && peak > 1
                          ? `${peak.toFixed(2)}x (${peakPct! >= 0 ? "+" : ""}${peakPct!.toFixed(0)}%)`
                          : "—"}
                      </td>
                      <td className="font-mono-display text-[var(--text-secondary)]">
                        {peak !== null && peak > 1.05 && w.peakAt
                          ? fmtDuration(w.addedAt, w.peakAt)
                          : "—"}
                      </td>
                      <td>
                        {prog !== null ? (
                          <div className="w-20 h-1.5 rounded-sm bg-[var(--bg-elevated)] overflow-hidden">
                            <div
                              className="h-full"
                              style={{ width: `${prog}%`, background: "var(--signal-long)" }}
                            />
                          </div>
                        ) : (
                          <span className="text-[var(--text-tertiary)]">—</span>
                        )}
                      </td>
                      <td>
                        <button
                          onClick={() => handleRemove(w.address)}
                          className="text-xs text-[var(--text-tertiary)] hover:text-[var(--signal-short)]"
                        >
                          remove
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="text-xs text-[var(--text-tertiary)] mt-2">
              Peak = best multiple observed since you added the token —
              it never resets, even if price round-trips. Peaks are sampled
              when prices refresh (every 60s while this tab is open), so
              spikes between checks can be missed.
            </p>
          </div>
        )}
      </div>

      {/* ── Trade log ─────────────────────────────────────────────── */}
      <div className="card">
        <h3 className="font-mono-display text-base mb-2">
          TRADE LOG ({trades.length})
        </h3>
        <div className="grid grid-cols-3 gap-2 mb-3">
          <Metric label="Win rate" value={trades.length ? `${Math.round((wins / trades.length) * 100)}%` : "—"} />
          <Metric label="Wins / Total" value={trades.length ? `${wins}/${trades.length}` : "—"} />
          <Metric
            label="Total PnL"
            value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`}
            color={totalPnl >= 0 ? "var(--signal-long)" : "var(--signal-short)"}
          />
        </div>
        {trades.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">
            No trades yet. Log them from the Challenge tab — the bankroll and
            this log share the same store.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Token</th><th>In</th><th>Out</th><th>PnL</th><th>Mult</th><th>When</th>
                </tr>
              </thead>
              <tbody>
                {[...trades].reverse().map((t, i) => (
                  <tr key={i}>
                    <td className="font-mono-display">{t.symbol}</td>
                    <td>${t.entryUsd.toFixed(2)}</td>
                    <td>${t.exitUsd.toFixed(2)}</td>
                    <td style={{ color: t.pnl >= 0 ? "var(--signal-long)" : "var(--signal-short)" }}>
                      {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}
                    </td>
                    <td className="font-mono-display">{t.multiple.toFixed(2)}x</td>
                    <td className="text-[var(--text-tertiary)]">{timeAgo(t.at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="rounded-input p-2" style={{ background: "var(--bg-elevated)" }}>
      <div className="text-xs text-[var(--text-tertiary)] font-mono-display uppercase">
        {label}
      </div>
      <div className="font-mono-display text-lg" style={{ color }}>
        {value}
      </div>
    </div>
  );
}
