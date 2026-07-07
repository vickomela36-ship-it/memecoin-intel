"use client";

import { useEffect, useMemo } from "react";
import useSWR from "swr";
import PerpTicketCard from "@/components/PerpTicketCard";
import AccuracyBadge from "@/components/AccuracyBadge";
import { buildAllTickets } from "@/modules/crypto/perps";
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
  const { data, error, isLoading } = useSWR("perp-desk", buildAllTickets, {
    refreshInterval,
    keepPreviousData: true,
    onErrorRetry: (_err, _key, _cfg, revalidate, { retryCount }) => {
      if (retryCount >= 3) return;
      setTimeout(() => revalidate({ retryCount }), 5000 * (retryCount + 1));
    },
  });

  const tickets = useMemo(() => data ?? [], [data]);
  const fetchedAt = useMemo(() => Date.now(), [data]);
  const actionable = useMemo(
    () => tickets.filter((t) => t.direction !== "STAND ASIDE"),
    [tickets]
  );

  // Strip: momentum shifting when any HIGH/MEDIUM conviction ticket exists
  useEffect(() => {
    onStatus(actionable.some((t) => t.confidence !== "LOW"));
  }, [actionable, onStatus]);

  // Log directional calls; resolve 24h later against current mark price
  useEffect(() => {
    if (!tickets.length) return;
    for (const t of actionable) {
      logSignal({
        module: "crypto",
        signal: {
          type: "perp",
          target: t.symbol,
          direction: t.direction === "LONG" ? "bullish" : "bearish",
          score: t.bias,
          details: { confidence: t.confidence, regime: t.regime },
        },
        priceAtSignal: t.markPrice,
      });
    }
    const priceBySymbol = new Map(tickets.map((t) => [t.symbol, t.markPrice]));
    for (const log of pendingLogs("crypto", DAY)) {
      const now = priceBySymbol.get(log.signal.target);
      if (now == null || log.outcome.priceAtSignal <= 0) continue;
      const move = now / log.outcome.priceAtSignal - 1;
      const hit =
        (log.signal.direction === "bullish" && move > 0) ||
        (log.signal.direction === "bearish" && move < 0);
      resolveLog(log.id, hit ? "hit" : "miss", now);
    }
    onLogged();
  }, [tickets, actionable, onLogged]);

  return (
    <div className="space-y-3">
      <div className="card flex items-center justify-between flex-wrap gap-2">
        <span className="font-mono-display text-sm text-[var(--text-secondary)]">
          PERP DESK · {tickets.length} symbols · {actionable.length} actionable ·
          funding + OI + taker flow + trend
        </span>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {error && !tickets.length
            ? "⚠ Binance unreachable"
            : isLoading && !data
              ? "loading positioning data…"
              : `updated ${timeAgo(fetchedAt)} · refresh ${refreshInterval / 1000}s`}
        </span>
      </div>

      {tickets.map((t) => (
        <PerpTicketCard key={t.symbol} ticket={t} />
      ))}

      {!tickets.length && error && (
        <div className="card text-sm text-[var(--signal-short)]">
          Binance futures API unreachable from this network. Data loads
          directly in your browser (Binance blocks datacenter IPs but allows
          browsers) — if this persists, your region may require a VPN.
        </div>
      )}
      {!tickets.length && !error && (
        <div className="card text-sm text-[var(--text-secondary)]">
          Loading funding, open interest, and flow data…
        </div>
      )}

      <AccuracyBadge module="crypto" />
    </div>
  );
}
