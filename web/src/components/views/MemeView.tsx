"use client";

import { useEffect, useMemo } from "react";
import useSWR from "swr";
import SignalCard from "@/components/SignalCard";
import RegimeBanner from "@/components/RegimeBanner";
import WhaleWatch from "@/components/WhaleWatch";
import AccuracyBadge from "@/components/AccuracyBadge";
import { fetchTokenPrice } from "@/modules/memecoin/fetchers";
import { instantSentiment } from "@/lib/sentiment";
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
  HOT: "hot",
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
  const { data, error, isLoading, isValidating } = useSWR(
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
  const hot = data?.hot ?? [];
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
      ...hot, ...trending, ...sure2x, ...recovery3x, ...momentum, ...volumePlays,
      ...higherCap, ...pumpfun, ...launches, ...degens,
    ],
    [hot, trending, sure2x, recovery3x, momentum, volumePlays, higherCap, pumpfun, launches, degens]
  );

  // Top pick per upside tier — highest CONVICTION SCORE within each tier, not a
  // prediction the token reaches the target. Higher tiers = higher risk.
  const highlights = useMemo(() => {
    const best = (arr: MemeSignal[]) =>
      arr.length ? arr.slice().sort((a, b) => b.score - a.score)[0] : null;
    const byTier = (t: string) => best(all.filter((s) => s.tier === t));
    return [
      { mult: "2x", anchor: "sec-sure", pick: best(sure2x) ?? byTier("3x POSSIBLE"), note: "Established, deep liquidity, buyers in control" },
      { mult: "3x", anchor: "sec-recovery", pick: best(recovery3x) ?? byTier("5x POTENTIAL"), note: "Deep-dip reversal, volume returning" },
      { mult: "5x", anchor: "sec-momentum", pick: byTier("5x POTENTIAL"), note: "Momentum/volume with headroom" },
      { mult: "10x", anchor: "sec-hot", pick: byTier("10x RUNNER"), note: "Fresh, small-cap, real attention" },
      { mult: "100x", anchor: "sec-degen", pick: byTier("100x MOONSHOT"), note: "Lottery tier — most go to zero" },
    ];
  }, [all, sure2x, recovery3x]);

  const navItems = [
    { id: "sec-hot", label: "HOT", n: hot.length },
    { id: "sec-trending", label: "TRENDING", n: trending.length },
    { id: "sec-sure", label: "2X", n: sure2x.length },
    { id: "sec-recovery", label: "3X", n: recovery3x.length },
    { id: "sec-momentum", label: "MOMENTUM", n: momentum.length },
    { id: "sec-volume", label: "VOLUME", n: volumePlays.length },
    { id: "sec-highcap", label: "HIGH-CAP", n: higherCap.length },
    { id: "sec-pump", label: "PUMP", n: pumpfun.length },
    { id: "sec-launch", label: "LAUNCH", n: launches.length },
    { id: "sec-degen", label: "DEGEN", n: degens.length },
  ].filter((x) => x.n > 0);

  const jump = (id: string) =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  useEffect(() => {
    onStatus(all.length > 0);
  }, [all, onStatus]);

  // Log fired signals + strong sentiment readings (measured over time)
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
      // Log high-confidence, directional sentiment so its predictive value
      // is measured (resolved directionally: bull ⇒ price up in 24h).
      const sent = instantSentiment({
        address: s.address, buySellRatio: s.buySellRatio, volH1: s.volH1,
        vol24h: s.vol24h, txns1h: s.txns1h, m5: s.m5, h1: s.h1,
      });
      if (sent.confidence >= 0.65 && Math.abs(sent.score) >= 40) {
        logSignal({
          module: "memecoin",
          signal: {
            type: sent.score > 0 ? "sentiment-bull" : "sentiment-bear",
            target: s.address,
            direction: sent.score > 0 ? "bullish" : "bearish",
            score: sent.score,
            details: { symbol: s.symbol, confidence: sent.confidence },
          },
          priceAtSignal: s.priceUsd,
        });
      }
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
        const entry = log.outcome.priceAtSignal;
        let hit: boolean;
        if (log.signal.type === "sentiment-bull") {
          hit = price > entry; // directional: predicted up
        } else if (log.signal.type === "sentiment-bear") {
          hit = price < entry; // predicted down
        } else {
          const mult = HIT_MULT[log.signal.type] ?? 1.5;
          hit = price >= entry * mult;
        }
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

  // Cold start — no data yet. Show a shaped skeleton, not a spinner, so the
  // terminal feels like it's assembling rather than blank-then-pop.
  if (isLoading && !data) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="scanning market">
        <div className="skeleton h-20 w-full" />
        <div className="skeleton h-12 w-full" />
        <div className="skeleton h-40 w-full" />
        <div className="skeleton h-40 w-full" />
        <p className="text-xs text-[var(--text-tertiary)] font-mono-display text-center pt-1">
          Running the shared market scan…
        </p>
      </div>
    );
  }

  // A refetch is in flight while we already have data on screen — dim the
  // stale numbers slightly so it's honest that they're one beat behind.
  const stale = isValidating && !!data;

  return (
    <div className={`space-y-3${stale ? " is-stale" : ""}`}>
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
                : isValidating
                  ? "refreshing…"
                  : `updated ${timeAgo(fetchedAt)}`}
            </span>
          </div>
          <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-12 gap-2 mt-3">
            <Stat label="Found" value={pulse.discovered} />
            <Stat label="Analyzed" value={pulse.analyzed} />
            <Stat label="Hot" value={hot.length} hot={hot.length > 0} />
            <Stat label="Trending" value={trending.length} />
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

      {/* ── HIGHLIGHTS — top pick per upside tier + jump nav ─────────── */}
      {all.length > 0 && (
        <>
          <div className="card">
            <div className="flex items-center justify-between mb-2 flex-wrap gap-1">
              <h2 className="font-display text-lg font-semibold">HIGHLIGHTS</h2>
              <span className="text-xs text-[var(--text-tertiary)]">top pick per upside tier</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {highlights.map((h) => {
                const clr =
                  h.mult === "100x" ? "var(--signal-edge)"
                    : h.mult === "5x" || h.mult === "10x" ? "var(--signal-neutral)"
                      : "var(--signal-long)";
                return (
                  <div key={h.mult} className="rounded-input p-2" style={{ background: "var(--bg-elevated)", border: `1px solid ${clr}33` }}>
                    <div className="font-display font-bold text-lg" style={{ color: clr }}>{h.mult}</div>
                    {h.pick ? (
                      <>
                        <button onClick={() => jump(h.anchor)} className="font-mono-display text-sm hover:underline block truncate w-full text-left">
                          ${h.pick.symbol}
                        </button>
                        <div className="text-xs text-[var(--text-tertiary)] font-mono-display">
                          score {h.pick.score} · {fmtUsd(h.pick.fdv)}
                        </div>
                        <button
                          onClick={() => window.dispatchEvent(new CustomEvent("mi:goto-safety", { detail: h.pick!.address }))}
                          className="text-xs text-[var(--signal-edge)] hover:underline mt-0.5"
                        >
                          safety ↗
                        </button>
                      </>
                    ) : (
                      <div className="text-xs text-[var(--text-tertiary)] mt-1">no pick right now</div>
                    )}
                    <div className="text-[10px] text-[var(--text-tertiary)] mt-1 leading-tight">{h.note}</div>
                  </div>
                );
              })}
            </div>
            <div className="text-[10px] text-[var(--text-tertiary)] mt-2">
              Ranked by our conviction score within each tier — NOT a prediction that a token reaches
              the target. Higher tiers carry higher risk. Not financial advice.
            </div>
          </div>

          {navItems.length > 1 && (
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {navItems.map((it) => (
                <button
                  key={it.id}
                  onClick={() => jump(it.id)}
                  className="whitespace-nowrap font-mono-display text-xs px-2.5 py-1 rounded-btn border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--border-active)] hover:text-[var(--text-primary)]"
                >
                  {it.label} <span className="text-[var(--text-tertiary)]">{it.n}</span>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── META OF THE DAY — which narrative is running ─────────────── */}
      {metas.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
            <h2 className="font-display text-lg font-semibold">META OF THE DAY</h2>
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
        anchor="sec-hot"
        title={`🔥 HOT — SNIPER FILTER (${hot.length})`}
        caption="The @web3_blizz recipe: <72h old, $10K+ liquidity, $200K–$1M mcap sweet spot, real attention, buyers in control — rugcheck-gated. The 20–40x hunting grounds. Size like moonshots."
        signals={hot}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-trending"
        title={`TRENDING NOW (${trending.length})`}
        caption="Raw attention across the whole scan, now VALIDATED: each token is graded LIKELY SEND / POSSIBLE / CHASING RISK on continuation signals, with a projected upside. The crowd is here — that cuts both ways."
        signals={trending}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-sure"
        title={`SURE PLAYS — 2x GRINDERS (${sure2x.length})`}
        caption="Highest-probability tier: established tokens, deep liquidity, buyers in control, bounce confirmed. Biggest size, smallest target — take the 1.5-2x and leave."
        signals={sure2x}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-recovery"
        title={`3x RECOVERY PLAYS (${recovery3x.length})`}
        caption="Deep-dip low-caps (-30% or worse) showing volume resurgence and reversal structure."
        signals={recovery3x}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-momentum"
        title={`MOMENTUM RIDERS (${momentum.length})`}
        caption="Already running with volume accelerating. Freshness-scored — chasing extended moves is penalized."
        signals={momentum}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-volume"
        title={`VOLUME PLAYS (${volumePlays.length})`}
        caption="Outsized turnover vs market cap with volume still building. Where the crowd concentrates, moves follow — confirm direction on the 5m first."
        signals={volumePlays}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-highcap"
        title={`HIGHER-CAP RECOVERY — $5M+ (${higherCap.length})`}
        caption="Established tokens dipping with buy-side sentiment intact. Core-play material."
        signals={higherCap}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-pump"
        title={`PUMP.FUN RELEASES (${pumpfun.length})`}
        caption="Fresh pump.fun tokens (<48h) with buyers in control and momentum — rugcheck DANGER tokens are filtered out of this section entirely."
        signals={pumpfun}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-launch"
        title={`NEW LAUNCHES (${launches.length})`}
        caption="Under 24h old with real liquidity and buy pressure. Earliest entries, thinnest data."
        signals={launches}
        fetchedAt={fetchedAt}
      />
      <Section
        anchor="sec-degen"
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
  anchor,
}: {
  title: string;
  caption: string;
  signals: MemeSignal[];
  fetchedAt: number;
  anchor?: string;
}) {
  if (!signals.length) return null;
  return (
    <>
      <div className="mt-2 scroll-mt-28" id={anchor}>
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        <p className="text-xs text-[var(--text-tertiary)]">{caption}</p>
      </div>
      {signals.map((s) => (
        <SignalCard key={`${s.mode}-${s.address}`} signal={s} fetchedAt={fetchedAt} />
      ))}
    </>
  );
}
