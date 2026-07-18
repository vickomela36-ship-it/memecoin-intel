"use client";

import { useEffect, useState } from "react";
import { computeRegime, type RegimeResult } from "@/lib/regime";
import { getChallenge } from "@/lib/storage";
import { getPositions } from "@/lib/discipline";

const STATE_COLOR = {
  HOT: "var(--signal-long)",
  NEUTRAL: "var(--signal-neutral)",
  COLD: "var(--signal-short)",
} as const;

/** Majors direction via CoinGecko 24h — cheap, no key. */
async function fetchMajorsUp(): Promise<number> {
  try {
    const res = await fetch(
      "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true",
      { cache: "no-store" }
    );
    if (!res.ok) return 1;
    const d = await res.json();
    return (
      Number(d?.bitcoin?.usd_24h_change > 0) +
      Number(d?.ethereum?.usd_24h_change > 0) +
      Number(d?.solana?.usd_24h_change > 0)
    );
  } catch {
    return 1;
  }
}

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
  const [regime, setRegime] = useState<RegimeResult | null>(null);
  const hit = recentHitRate();

  useEffect(() => {
    let cancelled = false;
    fetchMajorsUp().then((majorsUp) => {
      if (cancelled) return;
      setRegime(computeRegime({ breadthPct, medianH24, majorsUp }));
    });
    return () => {
      cancelled = true;
    };
  }, [breadthPct, medianH24]);

  if (!regime) return null;
  const clr = STATE_COLOR[regime.state];
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
          {regime.inputs.medianH24}% · majors {regime.inputs.majorsUp}/3 up
        </span>
      </div>
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
