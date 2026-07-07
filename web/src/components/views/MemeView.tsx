"use client";

import { useEffect, useMemo } from "react";
import useSWR from "swr";
import SignalCard from "@/components/SignalCard";
import AccuracyBadge from "@/components/AccuracyBadge";
import { runMemeScan } from "@/modules/memecoin/scanner";
import { fetchTokenPrice } from "@/modules/memecoin/fetchers";
import { logSignal, pendingLogs, resolveLog } from "@/lib/accuracy-tracker";
import { timeAgo } from "@/lib/utils";

const DAY = 24 * 3600 * 1000;
const HIT_MULT = { launch: 1.5, recovery: 1.2 }; // documented in tracker

export default function MemeView({
  onStatus,
  refreshInterval,
  onLogged,
}: {
  onStatus: (active: boolean) => void;
  refreshInterval: number;
  onLogged: () => void;
}) {
  const { data, error, isLoading } = useSWR("meme-scan", runMemeScan, {
    refreshInterval,
    keepPreviousData: true,
    onErrorRetry: (_err, _key, _cfg, revalidate, { retryCount }) => {
      if (retryCount >= 3) return;
      setTimeout(() => revalidate({ retryCount }), 5000 * (retryCount + 1));
    },
  });

  const fetchedAt = useMemo(() => Date.now(), [data]);
  const launches = data?.launches ?? [];
  const recoveries = data?.recoveries ?? [];
  const all = useMemo(() => [...launches, ...recoveries], [launches, recoveries]);

  useEffect(() => {
    onStatus(all.length > 0);
  }, [all, onStatus]);

  // Log fired signals; resolve pending ones older than 24h via refetch
  useEffect(() => {
    if (!all.length) return;
    for (const s of all) {
      if (s.priceUsd <= 0) continue;
      logSignal({
        module: "memecoin",
        signal: {
          type: s.mode.toLowerCase(),
          target: s.address,
          direction: "bullish",
          score: s.score,
          details: { symbol: s.symbol, fdv: s.fdv },
        },
        priceAtSignal: s.priceUsd,
      });
    }
    onLogged();
  }, [all, onLogged]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const pending = pendingLogs("memecoin", DAY).slice(0, 5); // rate-friendly
      for (const log of pending) {
        const price = await fetchTokenPrice(log.signal.target);
        if (cancelled) return;
        if (price === null) {
          // token disappeared from DexScreener = effectively dead
          resolveLog(log.id, "miss", null);
          continue;
        }
        const mult =
          log.signal.type === "launch" ? HIT_MULT.launch : HIT_MULT.recovery;
        const hit = price >= log.outcome.priceAtSignal * mult;
        resolveLog(log.id, hit ? "hit" : "miss", price);
      }
      if (pending.length) onLogged();
    })();
    return () => {
      cancelled = true;
    };
  }, [data, onLogged]);

  return (
    <div className="space-y-3">
      <div className="card flex items-center justify-between flex-wrap gap-2">
        <span className="font-mono-display text-sm text-[var(--text-secondary)]">
          Active signals: {all.length} · scanned {data?.scanned ?? 0} tokens ·
          thresholds: launch 65+, recovery 60+
        </span>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {error
            ? `⚠ DexScreener unreachable — last data ${timeAgo(fetchedAt)}`
            : isLoading && !data
              ? "scanning…"
              : `updated ${timeAgo(fetchedAt)}`}
        </span>
      </div>

      {launches.length > 0 && (
        <>
          <h2 className="font-mono-display text-lg mt-2">
            LAUNCH SIGNALS ({launches.length})
          </h2>
          {launches.map((s) => (
            <SignalCard key={s.address} signal={s} fetchedAt={fetchedAt} />
          ))}
        </>
      )}

      {recoveries.length > 0 && (
        <>
          <h2 className="font-mono-display text-lg mt-2">
            RECOVERY SIGNALS ({recoveries.length})
          </h2>
          {recoveries.map((s) => (
            <SignalCard key={s.address} signal={s} fetchedAt={fetchedAt} />
          ))}
        </>
      )}

      {all.length === 0 && !isLoading && !error && (
        <div className="card text-sm text-[var(--text-secondary)]">
          No tokens currently clear the signal thresholds. That is the system
          working — fewer, better signals. Check back after the next refresh.
        </div>
      )}
      {error && all.length === 0 && (
        <div className="card text-sm text-[var(--signal-short)]">
          DexScreener API unreachable. Retrying with backoff.
        </div>
      )}

      <AccuracyBadge module="memecoin" />
    </div>
  );
}
