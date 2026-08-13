"use client";

import useSWR from "swr";
import { computeRegime } from "@/lib/regime";
import { getChallenge } from "@/lib/storage";
import { getPositions } from "@/lib/discipline";
import { jsonFetcher } from "@/lib/utils";

interface MajorsResp {
  available: boolean;
  majors: { sym: string; state: string; up: boolean }[];
  majorsUp: number | null;
}
interface TrenchesResp {
  available: boolean;
  runnersThisWeek: number;
  seenThisWeek: number;
  freshLaunchMedianMcap: number;
  freshLaunchCount: number;
  graduationRate: number | null;
  graduationSamples: number;
}

const STATE_COLOR = {
  HOT: "var(--signal-long)",
  NEUTRAL: "var(--signal-neutral)",
  COLD: "var(--signal-short)",
} as const;

/** Recent user hit-rate: closed positions + challenge trades, last 10. */
function recentHitRate(): { rate: number | null; sample: number } {
  const posClosed: number[] = getPositions()
    .filter((p) => p.status === "CLOSED" && p.exitUsd !== null)
    .map((p) => (p.exitUsd! > p.sizeUsd ? 1 : 0));
  const trades: number[] = getChallenge().trades.map((t) => (t.pnl > 0 ? 1 : 0));
  const all: number[] = [...posClosed, ...trades].slice(-10);
  if (all.length < 3) return { rate: null, sample: all.length };
  return { rate: all.reduce((a, b) => a + b, 0) / all.length, sample: all.length };
}

export default function RegimeBanner({
  breadthPct,
  medianH24,
}: {
  breadthPct: number;
  medianH24: number;
}) {
  const hit = recentHitRate();
  // Real BTC/ETH/SOL structure when Binance answers; otherwise fall back to a
  // breadth-derived proxy so the dial never hard-depends on an external feed.
  const { data: majorsData } = useSWR<MajorsResp>("/api/majors", (u: string) => jsonFetcher<MajorsResp>(u), {
    refreshInterval: 600_000,
    revalidateOnFocus: false,
  });
  const proxyUp = breadthPct >= 55 ? 3 : breadthPct >= 45 ? 2 : breadthPct >= 35 ? 1 : 0;
  const realMajors = majorsData?.available && majorsData.majorsUp !== null;
  const majorsUp = realMajors ? majorsData!.majorsUp! : proxyUp;
  const regime = computeRegime({ breadthPct, medianH24, majorsUp });
  const clr = STATE_COLOR[regime.state];

  // Real trenches heat metrics from the creator ledger (measured, not proxied).
  const { data: trenches } = useSWR<TrenchesResp>("/api/trenches", (u: string) => jsonFetcher<TrenchesResp>(u), {
    refreshInterval: 300_000,
    revalidateOnFocus: false,
  });
  const coldWeek = regime.state === "COLD" && hit.rate !== null && hit.rate < 0.4;

  return (
    <div className="card" style={{ borderColor: clr }}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span
            className="font-mono-display text-sm px-2 py-0.5 rounded-input"
            style={{ color: clr, border: `1px solid ${clr}`, background: `${clr}15` }}
          >
            REGIME: {regime.state}
          </span>
          <span className="font-mono-display text-xs text-[var(--text-secondary)]">
            {regime.score}/100
          </span>
        </div>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          breadth {regime.inputs.breadthPct}% · median {regime.inputs.medianH24 >= 0 ? "+" : ""}
          {regime.inputs.medianH24}% ·{" "}
          {realMajors ? "majors" : "trenches"} {regime.inputs.majorsUp}/3
        </span>
      </div>
      {realMajors && (
        <div className="flex gap-3 mt-1 text-xs font-mono-display">
          {majorsData!.majors.map((m) => (
            <span key={m.sym} style={{ color: m.up ? "var(--signal-long)" : m.state === "DOWNTREND" ? "var(--signal-short)" : "var(--text-tertiary)" }}>
              {m.sym} {m.state === "UPTREND" ? "▲" : m.state === "DOWNTREND" ? "▼" : m.state === "REVERSAL FORMING" ? "↺" : "→"}
            </span>
          ))}
        </div>
      )}
      {trenches?.available && (
        <div className="flex gap-3 mt-1 text-xs font-mono-display text-[var(--text-tertiary)] flex-wrap">
          <span style={{ color: trenches.runnersThisWeek > 0 ? "var(--signal-long)" : undefined }}>
            {trenches.runnersThisWeek} ran &gt;10x / 7d
          </span>
          {trenches.freshLaunchCount > 0 && (
            <span>fresh-launch median ${(trenches.freshLaunchMedianMcap / 1000).toFixed(0)}K</span>
          )}
          {trenches.graduationRate !== null && (
            <span title={`${trenches.graduationSamples} samples, last 24h`}>
              graduation {trenches.graduationRate}%
            </span>
          )}
          {trenches.seenThisWeek > 0 && <span>{trenches.seenThisWeek} tracked this week</span>}
        </div>
      )}
      <div className="text-sm text-[var(--text-secondary)] mt-1">{regime.guidance}</div>
      <div className="text-xs text-[var(--text-tertiary)] mt-0.5">{regime.rotation}</div>
      {coldWeek && (
        <div className="text-xs mt-1" style={{ color: "var(--signal-neutral)" }}>
          Your recent hit rate ({Math.round(hit.rate! * 100)}% of {hit.sample}) is
          low AND the market is cold. This is a cold week — it is not you failing.
          The trap is trading harder into a dead tape. Trade less, not more.
        </div>
      )}
    </div>
  );
}
