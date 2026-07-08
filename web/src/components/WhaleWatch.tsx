"use client";

import useSWR from "swr";
import { fmtUsd, jsonFetcher } from "@/lib/utils";
import type { MemeSignal, WhaleTokenIntel } from "@/types";

function flagColor(flag: string): string {
  if (flag.startsWith("INSIDER-HEAVY") || flag.includes("DISTRIBUTING"))
    return "var(--signal-short)";
  if (flag.includes("ACCUMULATING")) return "var(--signal-long)";
  if (flag.startsWith("Concentrated")) return "var(--signal-neutral)";
  return "var(--text-secondary)";
}

export default function WhaleWatch({ signals }: { signals: MemeSignal[] }) {
  // Top signals across categories — dedupe by address, cap 8
  const seen = new Set<string>();
  const targets = signals.filter((s) => {
    if (seen.has(s.address)) return false;
    seen.add(s.address);
    return true;
  }).slice(0, 8);

  const key = targets.length
    ? `/api/whales?tokens=${targets.map((t) => `${t.address}|${t.symbol}`).join(",")}`
    : null;

  const { data, error, isLoading } = useSWR(
    key,
    (url: string) => jsonFetcher<WhaleTokenIntel[]>(url),
    { refreshInterval: 300_000, keepPreviousData: true }
  );

  if (!targets.length) return null;

  return (
    <div className="card">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <h2 className="font-mono-display text-lg">WHALE / INSIDER WATCH</h2>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {isLoading && !data ? "reading on-chain…" : "Helius RPC + Birdeye · 5m cache"}
        </span>
      </div>
      <p className="text-xs text-[var(--text-tertiary)] mb-2">
        Holder concentration and large-trade flow (&ge;$300 swaps) for the top
        signals above. Top holders include LP pools and CEX wallets — treat
        concentration as an upper bound, not proof of insiders.
      </p>

      {error && !data && (
        <div className="text-sm" style={{ color: "var(--signal-neutral)" }}>
          On-chain sources unreachable right now — signals still valid, whale
          layer will fill in when the APIs recover.
        </div>
      )}

      {data && (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Token</th>
                <th>Top 1</th>
                <th>Top 5</th>
                <th>Top 10</th>
                <th>Whale buys</th>
                <th>Whale sells</th>
                <th>Net flow</th>
                <th>Largest</th>
                <th>Read</th>
              </tr>
            </thead>
            <tbody>
              {data.map((w) => (
                <tr key={w.address}>
                  <td className="font-mono-display">${w.symbol}</td>
                  <td className="font-mono-display">
                    {w.top1Pct !== null ? `${w.top1Pct}%` : "—"}
                  </td>
                  <td className="font-mono-display">
                    {w.top5Pct !== null ? `${w.top5Pct}%` : "—"}
                  </td>
                  <td
                    className="font-mono-display"
                    style={{
                      color:
                        (w.top10Pct ?? 0) >= 70
                          ? "var(--signal-short)"
                          : (w.top10Pct ?? 0) >= 50
                            ? "var(--signal-neutral)"
                            : undefined,
                    }}
                  >
                    {w.top10Pct !== null ? `${w.top10Pct}%` : "—"}
                  </td>
                  <td className="font-mono-display" style={{ color: "var(--signal-long)" }}>
                    {w.whaleBuyUsd !== null ? fmtUsd(w.whaleBuyUsd) : "—"}
                  </td>
                  <td className="font-mono-display" style={{ color: "var(--signal-short)" }}>
                    {w.whaleSellUsd !== null ? fmtUsd(w.whaleSellUsd) : "—"}
                  </td>
                  <td
                    className="font-mono-display"
                    style={{
                      color:
                        w.netUsd === null
                          ? undefined
                          : w.netUsd >= 0
                            ? "var(--signal-long)"
                            : "var(--signal-short)",
                    }}
                  >
                    {w.netUsd !== null
                      ? `${w.netUsd >= 0 ? "+" : "-"}${fmtUsd(Math.abs(w.netUsd)).slice(1)}`
                      : "—"}
                  </td>
                  <td className="font-mono-display">
                    {w.largestTradeUsd !== null ? fmtUsd(w.largestTradeUsd) : "—"}
                  </td>
                  <td>
                    {w.flags.slice(0, 2).map((f) => (
                      <span
                        key={f}
                        className="text-xs font-mono-display block"
                        style={{ color: flagColor(f) }}
                      >
                        {f}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
