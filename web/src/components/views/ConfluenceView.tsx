"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { cx, fmtPrice, fmtUsd, jsonFetcher, timeAgo } from "@/lib/utils";
import { addWatch } from "@/lib/storage";
import type { MemeScanResult, MemeSignal } from "@/types";

interface HorizonProjection {
  hours: number;
  upsidePct: number; // projected possible upside over this horizon
  prob: number; // est. probability of reaching it
}

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
  horizons: HorizonProjection[];
  p2x: number;
  p5x: number;
  upsideBand: string;
  drivers: string;
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
 * Indicator-and-sentiment-driven horizon projections (1h / 4h / 8h / 24h).
 *
 * Drift comes from blended momentum velocity (1h move weighted heaviest,
 * then 6h and 24h pace), scaled by sentiment (buy/sell ratio) and volume
 * acceleration, compounding sub-linearly (momentum decays: h^0.75), and
 * capped by the category target band. Heuristic priors, NOT measured
 * frequencies — the Track Record panel is what verifies them.
 */
function estimate(rows: MemeSignal[]): Omit<ConfluenceRow, "address" | "symbol" | "name" | "priceUsd" | "fdv" | "liquidity" | "pairUrl" | "warnings"> {
  const avgScore = rows.reduce((a, s) => a + s.score, 0) / rows.length;
  const confluenceScore = Math.min(100, avgScore + 8 * (rows.length - 1));
  const octane = rows.some((s) => HIGH_OCTANE.has(s.playType));
  const first = rows[0];

  // ── Indicators ─────────────────────────────────────────────────────
  // Momentum velocity in %/hour, recent frames weighted heaviest
  const drift =
    0.45 * first.h1 + 0.35 * (first.h6 / 6) + 0.2 * (first.h24 / 24);

  // Sentiment multiplier from buy/sell pressure
  const bsr = first.buySellRatio;
  const sentMult = bsr >= 2 ? 1.3 : bsr >= 1.5 ? 1.15 : bsr >= 1 ? 1.0 : 0.7;

  // Volume acceleration multiplier (hourly pace vs 24h average)
  const volAccel =
    first.vol24h > 0 && first.volH1 > 0
      ? (first.volH1 * 24) / first.vol24h
      : 1;
  const volMult = volAccel >= 2 ? 1.25 : volAccel >= 1.5 ? 1.1 : volAccel >= 0.8 ? 1.0 : 0.85;

  // Confluence bonus: independent setups agreeing
  const confMult = 1 + 0.06 * (rows.length - 1);

  const maxTarget = Math.max(...rows.map((s) => TIER_TARGET[s.sizingKey] ?? 2));
  const minTarget = Math.min(...rows.map((s) => TIER_TARGET[s.sizingKey] ?? 2));

  // Volatility floor: even with flat drift, these tokens swing — bounce
  // potential from average absolute hourly range
  const volatilityPerH = Math.max(
    Math.abs(first.h1),
    Math.abs(first.h6) / 6,
    Math.abs(first.h24) / 24,
    1.5
  );

  const pBase = Math.min(80, Math.max(10, 15 + confluenceScore * 0.5));

  const horizons: HorizonProjection[] = [1, 4, 8, 24].map((h) => {
    // Momentum-driven projection with sub-linear persistence
    const momentumUp = Math.max(0, drift) * sentMult * volMult * confMult * Math.pow(h, 0.75);
    // Volatility bounce floor (mean-reversion potential when drift is flat/negative)
    const bounceUp = volatilityPerH * 0.5 * Math.pow(h, 0.5);
    let upside = Math.max(momentumUp, bounceUp);
    // Cap by the category band, scaled down for shorter horizons
    const capPct = (maxTarget * 100 - 100) * Math.min(1, h / 24 + 0.15);
    upside = Math.min(upside, capPct);

    // Probability: base from confluence, discounted on short horizons,
    // nudged by sentiment
    let prob = pBase * (0.55 + 0.45 * Math.pow(h / 24, 0.35));
    if (bsr >= 1.5) prob += h <= 4 ? 6 : 3;
    if (drift <= 0 && h <= 4) prob -= 8; // fighting the tape short-term
    prob = Math.min(85, Math.max(5, prob));

    return { hours: h, upsidePct: Math.round(upside), prob: Math.round(prob) };
  });

  const p30_24h = horizons[3].prob;
  const p2x = Math.round(p30_24h * (octane ? 0.5 : 0.35));
  const p5x = Math.round(p2x * (octane ? 0.4 : 0.2));

  const drivers =
    `1h ${first.h1 >= 0 ? "+" : ""}${first.h1.toFixed(1)}% · ` +
    `6h ${first.h6 >= 0 ? "+" : ""}${first.h6.toFixed(0)}% · ` +
    `B/S ${bsr.toFixed(1)}x (${sentMult > 1 ? "bullish" : sentMult < 1 ? "bearish" : "neutral"} sentiment) · ` +
    `vol pace ${volAccel.toFixed(1)}x (${volMult > 1 ? "accelerating" : volMult < 1 ? "fading" : "steady"}) · ` +
    `×${rows.length} confluence`;

  return {
    categories: rows.map((s) => ({
      playType: s.playType,
      score: s.score,
      sizingKey: s.sizingKey,
    })),
    avgScore: Math.round(avgScore),
    confluenceScore: Math.round(confluenceScore),
    horizons,
    p2x,
    p5x,
    upsideBand: minTarget === maxTarget ? `~${maxTarget}x` : `${minTarget}x–${maxTarget}x`,
    drivers,
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

            {/* Horizon projections — indicator + sentiment driven */}
            <div className="mt-3">
              <div className="text-xs font-mono-display text-[var(--text-tertiary)] uppercase mb-1">
                Possible upside by horizon
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {r.horizons.map((hz) => (
                  <div
                    key={hz.hours}
                    className="rounded-input px-2 py-1.5 text-center"
                    style={{ background: "var(--bg-elevated)" }}
                  >
                    <div className="text-xs text-[var(--text-tertiary)] font-mono-display">
                      {hz.hours}H
                    </div>
                    <div
                      className="font-mono-display text-lg"
                      style={{
                        color:
                          hz.upsidePct >= 30
                            ? "var(--signal-edge)"
                            : hz.upsidePct >= 10
                              ? "var(--signal-long)"
                              : "var(--text-secondary)",
                      }}
                    >
                      +{hz.upsidePct}%
                    </div>
                    <div className="text-xs font-mono-display text-[var(--text-secondary)]">
                      ~{hz.prob}% odds
                    </div>
                  </div>
                ))}
                <div className="rounded-input px-2 py-1.5 text-center" style={{ background: "var(--bg-elevated)" }}>
                  <div className="text-xs text-[var(--text-tertiary)] font-mono-display">BAND</div>
                  <div className="font-mono-display text-lg" style={{ color: "var(--signal-edge)" }}>
                    {r.upsideBand}
                  </div>
                  <div className="text-xs font-mono-display text-[var(--text-secondary)]">
                    2x ~{r.p2x}% · 5x ~{r.p5x}%
                  </div>
                </div>
              </div>
              <div className="text-xs text-[var(--text-tertiary)] font-mono-display mt-1">
                Drivers: {r.drivers}
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

