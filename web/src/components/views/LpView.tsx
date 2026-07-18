"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { cx, fmtUsd, jsonFetcher, timeAgo } from "@/lib/utils";
import type { LpCall, LpResult } from "@/types";

const CLASS_COLOR: Record<string, string> = {
  STABLE: "var(--signal-long)",
  BLUECHIP: "var(--signal-edge)",
  MEMECOIN: "var(--signal-short)",
};

function LpCard({ c }: { c: LpCall }) {
  const [open, setOpen] = useState(false);
  const clr = CLASS_COLOR[c.cls];
  return (
    <div className="card">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span
            className="font-mono-display text-xs px-2 py-0.5 rounded-input"
            style={{ color: clr, border: `1px solid ${clr}`, background: `${clr}15` }}
          >
            {c.strategy.shape}
          </span>
          <span className="font-mono-display text-lg">{c.name}</span>
        </div>
        <div className="text-right">
          <div className="font-mono-display text-lg" style={{ color: "var(--signal-long)" }}>
            ~{c.estAprPct.toLocaleString()}% APR
          </div>
          <div className="text-xs text-[var(--text-tertiary)] font-mono-display">
            {c.feeYieldDailyPct}%/day fees
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 mt-2 text-sm">
        <Stat label="TVL" value={fmtUsd(c.tvlUsd)} />
        <Stat label="Vol 24h" value={fmtUsd(c.vol24Usd)} />
        <Stat label="Fees 24h" value={fmtUsd(c.fees24Usd)} />
        <Stat label="Vol/TVL" value={`${c.volTvlRatio}x`} />
        <Stat label="Bin step" value={String(c.binStep)} />
        <Stat label="Base fee" value={`${c.baseFeePct}%`} />
        <Stat label="Quality" value={`${c.quality}/100`} />
        <Stat
          label="Bin fit"
          value={c.strategy.binStepMatch === "matched" ? "✓ matched" : "⚠ off"}
        />
      </div>

      {/* Strategy + entry */}
      <div className="mt-2 px-3 py-2 rounded-input text-sm font-mono-display" style={{ background: "var(--bg-elevated)", borderLeft: `3px solid ${clr}` }}>
        <div><span className="text-[var(--text-secondary)]">STRATEGY</span> {c.strategy.shape} · bin step {c.strategy.binStepReco} · {c.strategy.range}</div>
        <div className="mt-0.5"><span className="text-[var(--text-secondary)]">ENTRY</span> {c.strategy.entry}</div>
        <div className="mt-0.5 text-xs text-[var(--text-tertiary)]">{c.strategy.sided}</div>
      </div>

      <button onClick={() => setOpen(!open)} className="mt-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display">
        {open ? "▾" : "▸"} Management & risk
      </button>
      {open && (
        <div className="mt-1 text-xs text-[var(--text-secondary)] space-y-1">
          <div><b>Manage:</b> {c.strategy.manage}</div>
          <div><b>IL:</b> {c.strategy.ilNote}</div>
          {c.warnings.map((w) => (
            <div key={w} style={{ color: "var(--signal-neutral)" }}>⚠ {w}</div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mt-2">
        <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-xs font-mono-display text-[var(--signal-edge)] hover:underline">
          Open on Meteora ↗
        </a>
        <span className="text-xs text-[var(--text-tertiary)]">Not financial advice · LP carries IL + smart-contract risk</span>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between sm:block">
      <span className="text-xs text-[var(--text-tertiary)] font-mono-display uppercase tracking-wide block">{label}</span>
      <span className="font-mono-display text-sm">{value}</span>
    </div>
  );
}

function Section({ title, caption, calls }: { title: string; caption: string; calls: LpCall[] }) {
  if (!calls.length) return null;
  return (
    <>
      <div className="mt-2">
        <h2 className="font-mono-display text-lg">{title}</h2>
        <p className="text-xs text-[var(--text-tertiary)]">{caption}</p>
      </div>
      {calls.map((c) => <LpCard key={c.address} c={c} />)}
    </>
  );
}

export default function LpView() {
  const { data, error, isLoading } = useSWR("/api/lp", (u: string) => jsonFetcher<LpResult>(u), {
    refreshInterval: 300_000,
    keepPreviousData: true,
  });
  const [fetchedAt, setFetchedAt] = useState(0);
  useEffect(() => { if (data) setFetchedAt(Date.now()); }, [data]);

  return (
    <div className="space-y-3">
      <div className="text-xs text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded-card px-3 py-2">
        Live Meteora DLMM pools ranked by real fee yield, with a concrete
        strategy per pair (liquidity shape, bin step, range, entry, management).
        APR = fees/TVL × 365 from live 24h numbers — it&apos;s a snapshot, not a
        promise. LPing carries impermanent loss and smart-contract risk.
      </div>

      <div className="card flex items-center justify-between flex-wrap gap-2">
        <span className="font-mono-display text-sm text-[var(--text-secondary)]">
          {(data?.stable.length ?? 0) + (data?.bluechip.length ?? 0) + (data?.memecoin.length ?? 0)} LP calls · {data?.poolsScanned ?? 0} pools scanned
        </span>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {error ? "⚠ Meteora unreachable" : isLoading && !data ? "loading pools…" : `updated ${timeAgo(fetchedAt)}`}
        </span>
      </div>

      <Section
        title={`STABLE YIELD (${data?.stable.length ?? 0})`}
        caption="Stable/correlated pairs — Curve shape, tight range, near-zero IL. The safest LP yield. Depeg is the risk."
        calls={data?.stable ?? []}
      />
      <Section
        title={`BLUE-CHIP (${data?.bluechip.length ?? 0})`}
        caption="Majors (SOL/USDC, BTC, ETH…) — Spot shape, moderate range. Moderate IL, dynamic fees offset some of it."
        calls={data?.bluechip ?? []}
      />
      <Section
        title={`MEMECOIN LP — DIP CATCHER (${data?.memecoin.length ?? 0})`}
        caption="High fees, high risk. Bid-Ask single-sided dip-catcher: set your bottom bin at max drawdown, take 5–10%/day, cut below the line. Check safety first."
        calls={data?.memecoin ?? []}
      />

      {!isLoading && !data?.stable.length && !data?.bluechip.length && !data?.memecoin.length && (
        <div className="card text-sm text-[var(--text-secondary)]">
          No pools cleared the quality filters right now (TVL/volume floors). Meteora may be rate-limited — retry shortly.
        </div>
      )}
    </div>
  );
}
