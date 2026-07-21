"use client";

import { useEffect, useMemo } from "react";
import useSWR from "swr";
import SignalCard from "@/components/SignalCard";
import RegimeBanner from "@/components/RegimeBanner";
import WhaleWatch from "@/components/WhaleWatch";
import AccuracyBadge from "@/components/AccuracyBadge";
import { fetchTokenPrice } from "@/modules/memecoin/fetchers";
import { logSignal, pendingLogs, resolveLog } from "@/lib/accuracy-tracker";
import { fmtUsd, jsonFetcher, timeAgo } from "@/lib/utils";
import type { MemeScanResult, MemeSignal } from "@/types";

const DAY = 24 * 3600 * 1000;
// Hit multipliers by play type — shown in the Track Record definitions
const HIT_MULT: Record<string, number> = {
  "sure-2x": 1.3,
  "recovery-3x": 1.3,
  momentum: 1.3,
  volume: 1.3,
  "higher-cap": 1.2,
  pumpfun: 1.5,
  launch: 1.5,
  degen: 1.5,
  trending: 1.3,
};

const LOG_TYPE: Record<MemeSignal["mode"], string> = {
  SURE: "sure-2x",
  RECOVERY: "recovery-3x",
  MOMENTUM: "momentum",
  VOLUME: "volume",
  "HIGHER-CAP": "higher-cap",
  PUMPFUN: "pumpfun",
  LAUNCH: "launch",
  DEGEN: "degen",
  TRENDING: "trending",
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
  // Server route runs ONE shared scan per minute for all visitors
  const { data, error, isLoading } = useSWR(
    "/api/scan",
    (url: string) => jsonFetcher<MemeScanResult>(url),
    {
      refreshInterval,
      keepPreviousData: true,
      onErrorRetry: (_err, _key, _cfg, revalidate, { retryCount }) => {
        if (retryCount >= 3) return;
        setTimeout(() => revalidate({ retryCount }), 5000 * (retryCount + 1));
      },
    }
  );

  const fetchedAt = useMemo(() => Date.now(), [data]);
  const trending = data?.trending ?? [];
  const sure2x = data?.sure2x ?? [];
  const recovery3x = data?.recovery3x ?? [];
  const momentum = data?.momentum ?? [];
  const volumePlays = data?.volumePlays ?? [];
  const higherCap = data?.higherCap ?? [];
  const pumpfun = data?.pumpfun ?? [];
  const launches = data?.launches ?? [];
  const degens = data?.degens ?? [];
  const metas = data?.metas ?? [];
  const pulse = data?.pulse;
  const all = useMemo(
    () => [
      ...trending, ...sure2x, ...recovery3x, ...momentum, ...volumePlays,
      ...higherCap, ...pumpfun, ...launches, ...degens,
    ],
    [trending, sure2x, recovery3x, momentum, volumePlays, higherCap, pumpfun, launches, degens]
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
          details: { symbol: s.symbol, fdv: s.fdv, playType: s.playType },
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

  const marketClr =
    (pulse?.greenPct ?? 50) >= 55
      ? "var(--signal-long)"
      : (pulse?.greenPct ?? 50) <= 35
        ? "var(--signal-short)"
        : "var(--signal-neutral)";

  return (
    <div className="space-y-3">
      {/* ── Market pulse + scan stats (the Streamlit stats row) ────────── */}
      {pulse && (
        <div className="card">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="font-mono-display text-sm" style={{ color: marketClr }}>
              MARKET PULSE: {pulse.greenPct}% green · median 24h{" "}
              {pulse.medianH24 >= 0 ? "+" : ""}
              {pulse.medianH24}% · {fmtUsd(pulse.totalVol24hUsd)} combined vol
            </span>
            <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
              {error
                ? `⚠ scan API unreachable — last data ${timeAgo(fetchedAt)}`
                : isLoading && !data
                  ? "scanning…"
                  : `updated ${timeAgo(fetchedAt)}`}
            </span>
          </div>
          <div className="grid grid-cols-5 sm:grid-cols-10 gap-2 mt-3">
            <Stat label="Found" value={pulse.discovered} />
            <Stat label="Analyzed" value={pulse.analyzed} />
            <Stat label="2x Grind" value={sure2x.length} hot={sure2x.length > 0} />
            <Stat label="3x Rec" value={recovery3x.length} />
            <Stat label="Momentum" value={momentum.length} />
            <Stat label="Volume" value={volumePlays.length} />
            <Stat label="High-cap" value={higherCap.length} />
            <Stat label="Pumpfun" value={pumpfun.length} hot={pumpfun.length > 0} />
            <Stat label="Launch" value={launches.length} />
            <Stat label="Degen" value={degens.length} />
          </div>
        </div>
      )}

      {/* ── REGIME DIAL — trade less when conditions are bad ─────────── */}
      {pulse && (
        <RegimeBanner breadthPct={pulse.greenPct} medianH24={pulse.medianH24} />
      )}

      {/* ── META OF THE DAY — which narrative is running ─────────────── */}
      {metas.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
            <h2 className="font-mono-display text-lg">META OF THE DAY</h2>
            <span
              className="font-mono-display text-sm pulse-live"
              style={{ color: "var(--signal-edge)" }}
            >
              {metas[0].name} — {metas[0].greenPct}% green, median{" "}
              {metas[0].medianH24 >= 0 ? "+" : ""}
              {metas[0].medianH24}%
            </span>
          </div>
          <p className="text-xs text-[var(--text-tertiary)] mb-2">
            Narratives ranked by breadth and median 24h move across all{" "}
            {pulse?.analyzed ?? 0} analyzed tokens. Trade the meta, not the
            straggler — money rotates by narrative.
          </p>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Narrative</th>
                  <th>Tokens</th>
                  <th>% Green</th>
                  <th>Median 24h</th>
                  <th>24h Volume</th>
                  <th>Leaders</th>
                </tr>
              </thead>
              <tbody>
                {metas.map((m, i) => (
                  <tr key={m.name}>
                    <td
                      className="font-mono-display"
                      style={{ color: i === 0 ? "var(--signal-edge)" : undefined }}
                    >
                      {i === 0 ? "🔥 " : ""}
                      {m.name}
                    </td>
                    <td className="font-mono-display">{m.tokens}</td>
                    <td
                      className="font-mono-display"
                      style={{
                        color:
                          m.greenPct >= 55
                            ? "var(--signal-long)"
                            : m.greenPct <= 35
                              ? "var(--signal-short)"
                              : undefined,
                      }}
                    >
                      {m.greenPct}%
                    </td>
                    <td
                      className="font-mono-display"
                      style={{
                        color:
                          m.medianH24 >= 0
                            ? "var(--signal-long)"
                            : "var(--signal-short)",
                      }}
                    >
                      {m.medianH24 >= 0 ? "+" : ""}
                      {m.medianH24}%
                    </td>
                    <td className="font-mono-display">{fmtUsd(m.totalVolUsd)}</td>
                    <td className="font-mono-display text-[var(--text-secondary)]">
                      {m.topSymbols.map((s) => `$${s}`).join(" ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Whale / insider layer for the strongest signals */}
      {all.length > 0 && (
        <WhaleWatch
          signals={[
            ...sure2x.slice(0, 2),
            ...momentum.slice(0, 2),
            ...pumpfun.slice(0, 1),
            ...recovery3x.slice(0, 1),
            ...launches.slice(0, 1),
            ...degens.slice(0, 1),
          ]}
        />
      )}

      <Section
        title={`TRENDING NOW (${trending.length})`}
        caption="Raw attention: highest transaction count + live volume across the whole scan, regardless of setup. The crowd is here — that cuts both ways. Safety-check before entry."
        signals={trending}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`SURE PLAYS — 2x GRINDERS (${sure2x.length})`}
        caption="Highest-probability tier: established tokens, deep liquidity, buyers in control, bounce confirmed. Biggest size, smallest target — take the 1.5-2x and leave."
        signals={sure2x}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`3x RECOVERY PLAYS (${recovery3x.length})`}
        caption="Deep-dip low-caps (-30% or worse) showing volume resurgence and reversal structure."
        signals={recovery3x}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`MOMENTUM RIDERS (${momentum.length})`}
        caption="Already running with volume accelerating. Freshness-scored — chasing extended moves is penalized."
        signals={momentum}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`VOLUME PLAYS (${volumePlays.length})`}
        caption="Outsized turnover vs market cap with volume still building. Where the crowd concentrates, moves follow — confirm direction on the 5m first."
        signals={volumePlays}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`HIGHER-CAP RECOVERY — $5M+ (${higherCap.length})`}
        caption="Established tokens dipping with buy-side sentiment intact. Core-play material."
        signals={higherCap}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`PUMP.FUN RELEASES (${pumpfun.length})`}
        caption="Fresh pump.fun tokens (<48h) with buyers in control and momentum — rugcheck DANGER tokens are filtered out of this section entirely."
        signals={pumpfun}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`NEW LAUNCHES (${launches.length})`}
        caption="Under 24h old with real liquidity and buy pressure. Earliest entries, thinnest data."
        signals={launches}
        fetchedAt={fetchedAt}
      />
      <Section
        title={`DEGEN MOONSHOTS (${degens.length})`}
        caption="5x / 10x / 100x POTENTIAL tiers. Rugchecked where possible. Only bet what you can lose — most go to zero."
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
          Scan API unreachable. Retrying with backoff.
        </div>
      )}

      <AccuracyBadge module="memecoin" />
    </div>
  );
}

function Stat({
  label,
  value,
  hot = false,
}: {
  label: string;
  value: number;
  hot?: boolean;
}) {
  return (
    <div
      className="rounded-input px-2 py-1.5 text-center"
      style={{ background: "var(--bg-elevated)" }}
    >
      <div
        className="font-mono-display text-lg tabular-nums"
        style={{ color: hot ? "var(--signal-edge)" : undefined }}
      >
        {value}
      </div>
      <div className="text-xs text-[var(--text-tertiary)] font-mono-display uppercase">
        {label}
      </div>
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
