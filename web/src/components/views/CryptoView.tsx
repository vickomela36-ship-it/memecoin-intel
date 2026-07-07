"use client";

import { useEffect, useMemo } from "react";
import useSWR from "swr";
import HeatmapGrid from "@/components/HeatmapGrid";
import AccuracyBadge from "@/components/AccuracyBadge";
import { fetchCryptoUniverse } from "@/modules/crypto/fetchers";
import { computeCryptoScore } from "@/modules/crypto/score";
import { logSignal, pendingLogs, resolveLog } from "@/lib/accuracy-tracker";
import { timeAgo } from "@/lib/utils";

const DAY = 24 * 3600 * 1000;

export default function CryptoView({
  onStatus,
  refreshInterval,
  onLogged,
}: {
  onStatus: (active: boolean) => void;
  refreshInterval: number;
  onLogged: () => void;
}) {
  const { data, error, isLoading } = useSWR("crypto-universe", fetchCryptoUniverse, {
    refreshInterval,
    keepPreviousData: true,
    onErrorRetry: (_err, _key, _cfg, revalidate, { retryCount }) => {
      if (retryCount >= 3) return;
      setTimeout(() => revalidate({ retryCount }), 5000 * (retryCount + 1));
    },
  });

  const rows = useMemo(
    () => (data ?? []).map(computeCryptoScore).sort((a, b) => b.score - a.score),
    [data]
  );

  const fetchedAt = useMemo(() => Date.now(), [data]);

  // Signal strip: momentum shifting when any token is 30+ points off neutral
  useEffect(() => {
    onStatus(rows.some((r) => Math.abs(r.score - 50) >= 30));
  }, [rows, onStatus]);

  // Log directional signals + resolve 24h-old ones against current prices
  useEffect(() => {
    if (!rows.length) return;
    for (const r of rows) {
      if (r.direction === "neutral") continue;
      logSignal({
        module: "crypto",
        signal: {
          type: "score",
          target: r.id,
          direction: r.direction,
          score: r.score,
          details: { label: r.label },
        },
        priceAtSignal: r.price,
      });
    }
    const priceById = new Map(rows.map((r) => [r.id, r.price]));
    for (const log of pendingLogs("crypto", DAY)) {
      const now = priceById.get(log.signal.target);
      if (now == null || log.outcome.priceAtSignal <= 0) continue;
      const move = now / log.outcome.priceAtSignal - 1;
      const hit =
        (log.signal.direction === "bullish" && move > 0) ||
        (log.signal.direction === "bearish" && move < 0);
      resolveLog(log.id, hit ? "hit" : "miss", now);
    }
    onLogged();
  }, [rows, onLogged]);

  return (
    <div className="space-y-3">
      <div className="card flex items-center justify-between flex-wrap gap-2">
        <span className="font-mono-display text-sm text-[var(--text-secondary)]">
          {rows.length} tokens scored · top-20 by mcap + top meme category
        </span>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {error
            ? `⚠ CoinGecko unreachable — showing last data (${timeAgo(fetchedAt)})`
            : isLoading && !data
              ? "loading…"
              : `updated ${timeAgo(fetchedAt)} · auto-refresh ${refreshInterval / 1000}s`}
        </span>
      </div>

      {rows.length > 0 ? (
        <HeatmapGrid rows={rows} />
      ) : error ? (
        <div className="card text-sm text-[var(--signal-short)]">
          CoinGecko API unreachable. Retrying automatically — the page stays up,
          data will fill in when the API recovers.
        </div>
      ) : (
        <div className="card text-sm text-[var(--text-secondary)]">Loading market data…</div>
      )}

      <AccuracyBadge module="crypto" />
    </div>
  );
}
