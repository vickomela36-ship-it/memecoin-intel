"use client";

import { useEffect, useMemo } from "react";
import useSWR from "swr";
import SignalCard from "@/components/SignalCard";
import AccuracyBadge from "@/components/AccuracyBadge";
import { runMemeScan } from "@/modules/memecoin/scanner";
import { fetchTokenPrice } from "@/modules/memecoin/fetchers";
import { logSignal, pendingLogs, resolveLog } from "@/lib/accuracy-tracker";
import { timeAgo } from "@/lib/utils";
import type { MemeSignal } from "@/types";

const DAY = 24 * 3600 * 1000;
// Hit multipliers by signal type — shown in the Track Record definitions
const HIT_MULT: Record<string, number> = {
  launch: 1.5,
  recovery: 1.2,
  "higher-cap": 1.2,
  degen: 1.5,
};

const LOG_TYPE: Record<MemeSignal["mode"], string> = {
  LAUNCH: "launch",
  RECOVERY: "recovery",
  "HIGHER-CAP": "higher-cap",
  DEGEN: "degen",
};

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
  const higherCap = data?.higherCap ?? [];
  const degens = data?.degens ?? [];
  const all = useMemo(
    () => [...launches, ...recoveries, ...higherCap, ...degens],
    [launches, recoveries, higherCap, degens]
  );

  useEffect(() => {
    onStatus(all.length > 0);
  }, [all, onStatus]);

  // Log fired signals
  useEffect(() => {
    if (!all.length) return;
    for (const s of all) {
      if (s.priceUsd <= 0) continue;
      logSignal({
        module: "memecoin",
        signal: {
          type: LOG_TYPE[s.mode],
          target: s.address,
          direction: "bullish",
          score: s.score,
          details: { symbol: s.symbol, fdv: s.fdv, tier: s.tier ?? null },
        },
        priceAtSignal: s.priceUsd,
      });
    }
    onLogged();
  }, [all, onLogged]);

  // Resolve signals older than 24h against a fresh price
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const pending = pendingLogs("memecoin", DAY).slice(0, 5); // rate-friendly
      for (const log of pending) {
        const price = await fetchTokenPrice(log.signal.target);
        if (cancelled) return;
        if (price === null) {
          resolveLog(log.id, "miss", null); // vanished from DexScreener = dead
          continue;
        }
        const mult = HIT_MULT[log.signal.type] ?? 1.5;
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
          launch 65+ / recovery 60+ / degen 45+
        </span>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {error
            ? `⚠ DexScreener unreachable — last data ${timeAgo(fetchedAt)}`
            : isLoading && !data
              ? "scanning…"
              : `updated ${timeAgo(fetchedAt)}`}
        </span>
      </div>

      <Section
        title={`NEW LAUNCHES (${launches.length})`}
        caption="Under 24h old with real liquidity and buy pressure. Earliest entries, thinnest data."
        signals={launches}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`LOW-CAP RECOVERY (${recoveries.length})`}
        caption="7-90 day tokens in a drawdown showing volume resurgence — graded A/B/C."
        signals={recoveries}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`HIGHER-CAP RECOVERY — $5M+ (${higherCap.length})`}
        caption="Established tokens dipping with buy-side sentiment intact. Core-play material."
        signals={higherCap}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`DEGEN PLAYS — RISKY GEMS (${degens.length})`}
        caption="Moonshot-tiered (3x / 5x / 10x / 100x potential). Rugchecked where possible. Only bet what you can lose."
        signals={degens}
        fetchedAt={fetchedAt}
      />

      {all.length === 0 && !isLoading && !error && (
        <div className="card text-sm text-[var(--text-secondary)]">
          No tokens currently clear any signal threshold. That is the system
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

function Section({
  title,
  caption,
  signals,
  fetchedAt,
}: {
  title: string;
  caption: string;
  signals: MemeSignal[];
  fetchedAt: number;
}) {
  if (!signals.length) return null;
  return (
    <>
      <div className="mt-2">
        <h2 className="font-mono-display text-lg">{title}</h2>
        <p className="text-xs text-[var(--text-tertiary)]">{caption}</p>
      </div>
      {signals.map((s) => (
        <SignalCard key={`${s.mode}-${s.address}`} signal={s} fetchedAt={fetchedAt} />
      ))}
    </>
  );
}
