"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { cx, fmtPrice, fmtUsd, jsonFetcher, timeAgo } from "@/lib/utils";
import { addWatch } from "@/lib/storage";
import type { MemeScanResult, MemeSignal } from "@/types";

interface ConfluenceRow {
  address: string;
  symbol: string;
  name: string;
  priceUsd: number;
  fdv: number;
  liquidity: number;
  pairUrl: string;
  categories: { playType: string; score: number; sizingKey: string }[];
  avgScore: number;
  confluenceScore: number;
  p30: number; // est. probability of +30% in 24h
  p2x: number;
  p5x: number;
  upsideBand: string;
  warnings: string[];
}

/** Max realistic target implied by a sizing tier. */
const TIER_TARGET: Record<string, number> = {
  A: 2,
  B: 3,
  "3x POSSIBLE": 3,
  "5x POTENTIAL": 5,
  "10x RUNNER": 10,
  "100x MOONSHOT": 20,
};

const HIGH_OCTANE = new Set(["10x RUNNER", "100x MOONSHOT", "NEW LAUNCH", "PUMPFUN RELEASE"]);

/**
 * Estimated upside probabilities. These are heuristic priors derived from
 * signal scores and category overlap — NOT measured frequencies. The Track
 * Record panel measures reality; these get recalibrated against it.
 */
function estimate(rows: MemeSignal[]): Omit<ConfluenceRow, "address" | "symbol" | "name" | "priceUsd" | "fdv" | "liquidity" | "pairUrl" | "warnings"> {
  const avgScore = rows.reduce((a, s) => a + s.score, 0) / rows.length;
  const confluenceScore = Math.min(100, avgScore + 8 * (rows.length - 1));

  const octane = rows.some((s) => HIGH_OCTANE.has(s.playType));
  const p30 = Math.round(Math.min(80, Math.max(10, 15 + confluenceScore * 0.5)));
  const p2x = Math.round(p30 * (octane ? 0.5 : 0.35));
  const p5x = Math.round(p2x * (octane ? 0.4 : 0.2));

  const maxTarget = Math.max(
    ...rows.map((s) => TIER_TARGET[s.sizingKey] ?? 2)
  );
  const minTarget = Math.min(
    ...rows.map((s) => TIER_TARGET[s.sizingKey] ?? 2)
  );

  return {
    categories: rows.map((s) => ({
      playType: s.playType,
      score: s.score,
      sizingKey: s.sizingKey,
    })),
    avgScore: Math.round(avgScore),
    confluenceScore: Math.round(confluenceScore),
    p30,
    p2x,
    p5x,
    upsideBand: minTarget === maxTarget ? `~${maxTarget}x` : `${minTarget}x–${maxTarget}x`,
  };
}

export default function ConfluenceView() {
  const { data, error, isLoading } = useSWR(
    "/api/scan",
    (url: string) => jsonFetcher<MemeScanResult>(url),
    { refreshInterval: 60_000, keepPreviousData: true }
  );
  const fetchedAt = useMemo(() => Date.now(), [data]);
  const [watched, setWatched] = useState<Record<string, boolean>>({});

  const rows = useMemo<ConfluenceRow[]>(() => {
    if (!data) return [];
    const byAddress = new Map<string, MemeSignal[]>();
    const sections: MemeSignal[][] = [
      data.sure2x, data.recovery3x, data.momentum, data.volumePlays,
      data.higherCap, data.pumpfun, data.launches, data.degens,
    ];
    for (const section of sections ?? []) {
      for (const s of section ?? []) {
        const list = byAddress.get(s.address) ?? [];
        // one entry per category
        if (!list.some((x) => x.playType === s.playType)) list.push(s);
        byAddress.set(s.address, list);
      }
    }

    const out: ConfluenceRow[] = [];
    byAddress.forEach((list) => {
      if (list.length < 2) return;
      const first = list[0];
      const warnings = Array.from(
        new Set(list.flatMap((s) => s.warnings.filter((w) => w.startsWith("RUGCHECK") || w.startsWith("Exit trap"))))
      );
      out.push({
        address: first.address,
        symbol: first.symbol,
        name: first.name,
        priceUsd: first.priceUsd,
        fdv: first.fdv,
        liquidity: first.liquidity,
        pairUrl: first.pairUrl,
        warnings,
        ...estimate(list),
      });
    });
    return out.sort(
      (a, b) =>
        b.categories.length - a.categories.length ||
        b.confluenceScore - a.confluenceScore
    );
  }, [data]);

  const strong = rows.filter((r) => r.categories.length >= 3);

  function handleWatch(r: ConfluenceRow) {
    addWatch({
      address: r.address,
      symbol: r.symbol,
      name: r.name,
      entryPrice: r.priceUsd,
      target2x: r.priceUsd * 2,
      grade: `CONFLUENCE x${r.categories.length}`,
      pairUrl: r.pairUrl,
    });
    setWatched((w) => ({ ...w, [r.address]: true }));
  }

  return (
    <div className="space-y-3">
      <div className="card flex items-center justify-between flex-wrap gap-2">
        <span className="font-mono-display text-sm text-[var(--text-secondary)]">
          CONFLUENCE — tokens firing in 2+ play categories at once ·{" "}
          {rows.length} found · {strong.length} in 3+
        </span>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {isLoading && !data ? "scanning…" : `updated ${timeAgo(fetchedAt)}`}
        </span>
      </div>
      <p className="text-xs text-[var(--text-tertiary)] px-1 -mt-1">
        When independent setups agree — a dip recovery that is ALSO a volume
        play ALSO riding momentum — conviction compounds. Upside odds are
        heuristic estimates from score + overlap, not guarantees; the Track
        Record panel is what verifies them over time.
      </p>

      {rows.map((r) => {
        const isStrong = r.categories.length >= 3;
        return (
          <div key={r.address} className={cx("card", isStrong && "edge-glow")}>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="font-mono-display text-xs px-2 py-0.5 rounded-input pulse-live"
                  style={{
                    color: "var(--signal-edge)",
                    border: "1px solid var(--signal-edge)",
                    background: "var(--accent-glow)",
                  }}
                >
                  {isStrong ? "STRONG " : ""}CONFLUENCE ×{r.categories.length}
                </span>
                <span className="font-mono-display text-lg">${r.symbol}</span>
                <span className="text-sm text-[var(--text-secondary)] hidden sm:inline">
                  {r.name.slice(0, 22)}
                </span>
              </div>
              <span className="font-mono-display text-sm text-[var(--text-secondary)]">
                {fmtPrice(r.priceUsd)} · MCap {fmtUsd(r.fdv)} · Liq {fmtUsd(r.liquidity)}
              </span>
            </div>

            {/* Category chips with per-category scores */}
            <div className="flex gap-2 mt-2 flex-wrap">
              {r.categories.map((c) => (
                <span
                  key={c.playType}
                  className="font-mono-display text-xs px-2 py-0.5 rounded-input border border-[var(--border-subtle)] text-[var(--text-secondary)]"
                >
                  {c.playType} <b className="text-[var(--text-primary)]">{c.score}</b>
                </span>
              ))}
              <span className="font-mono-display text-xs px-2 py-0.5 rounded-input"
                style={{ color: "var(--signal-edge)", border: "1px solid var(--border-active)" }}>
                confluence {r.confluenceScore}
              </span>
            </div>

            {/* Estimated upside strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
              <Odds label="+30% in 24h" pct={r.p30} />
              <Odds label="2x" pct={r.p2x} />
              <Odds label="5x" pct={r.p5x} />
              <div className="rounded-input px-2 py-1.5 text-center" style={{ background: "var(--bg-elevated)" }}>
                <div className="font-mono-display text-lg" style={{ color: "var(--signal-edge)" }}>
                  {r.upsideBand}
                </div>
                <div className="text-xs text-[var(--text-tertiary)] font-mono-display uppercase">
                  target band
                </div>
              </div>
            </div>

            {r.warnings.length > 0 && (
              <div className="mt-2 text-xs" style={{ color: "var(--signal-short)" }}>
                ⚠ {r.warnings.slice(0, 2).join(" · ")}
              </div>
            )}

            <div className="flex items-center justify-between mt-2 flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleWatch(r)}
                  className="text-xs font-mono-display px-2 py-1 rounded-btn border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--border-active)]"
                >
                  {watched[r.address] ? "✓ Watching" : "+ Watch"}
                </button>
                <a
                  href={`https://jup.ag/swap/SOL-${r.address}`}
                  target="_blank" rel="noopener noreferrer"
                  className="text-xs font-mono-display px-2 py-1 rounded-btn"
                  style={{ color: "var(--signal-long)", border: "1px solid var(--signal-long)" }}
                >
                  BUY (Jupiter) ↗
                </a>
                {r.pairUrl && (
                  <a href={r.pairUrl} target="_blank" rel="noopener noreferrer"
                    className="text-xs font-mono-display text-[var(--signal-edge)] hover:underline">
                    DexScreener ↗
                  </a>
                )}
              </div>
              <span className="text-xs text-[var(--text-tertiary)]">
                Estimates, not promises. Not financial advice.
              </span>
            </div>
          </div>
        );
      })}

      {!rows.length && !isLoading && (
        <div className="card text-sm text-[var(--text-secondary)]">
          No token is currently firing in 2+ categories. Confluence is rare by
          design — when it appears, it matters.
        </div>
      )}
      {error && !data && (
        <div className="card text-sm text-[var(--signal-short)]">
          Scan API unreachable. Retrying.
        </div>
      )}
    </div>
  );
}

function Odds({ label, pct }: { label: string; pct: number }) {
  const clr =
    pct >= 50 ? "var(--signal-long)" : pct >= 25 ? "var(--signal-neutral)" : "var(--text-secondary)";
  return (
    <div className="rounded-input px-2 py-1.5 text-center" style={{ background: "var(--bg-elevated)" }}>
      <div className="font-mono-display text-lg" style={{ color: clr }}>
        ~{pct}%
      </div>
      <div className="text-xs text-[var(--text-tertiary)] font-mono-display uppercase">{label}</div>
    </div>
  );
}
