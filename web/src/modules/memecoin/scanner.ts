import type { DexPair, MemeScanResult, MemeSignal, ScanPulse } from "@/types";
import { bestSolanaPair, discoverTokens, fetchPairsBatch } from "./fetchers";
import {
  LAUNCH_MIN,
  MOMENTUM_MIN,
  RECOVERY_MIN,
  SURE2X_MIN,
  scoreLaunch,
  scoreMomentum,
  scoreRecovery,
  scoreSure2x,
} from "./scoring";
import { computeMoonshot } from "./moonshot";

const HIGH_CAP_FDV = 5_000_000;

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

function buySellRatio(pair: DexPair): number {
  let ratio = 0;
  for (const tf of ["m5", "h1"] as const) {
    const t = pair.txns?.[tf];
    const buys = num(t?.buys);
    const sells = num(t?.sells);
    if (sells > 0) ratio = Math.max(ratio, buys / sells);
    else if (buys > 5) ratio = Math.max(ratio, 3);
  }
  return ratio;
}

function baseSignal(
  pair: DexPair,
  mode: MemeSignal["mode"],
  playType: string,
  ageHours: number,
  boosts: number,
  scored: {
    score: number;
    components: MemeSignal["components"];
    reasons: string[];
    warnings: string[];
  },
  sizingKey: string
): MemeSignal {
  const t1h = pair.txns?.h1;
  return {
    mode,
    playType,
    address: pair.baseToken?.address ?? "",
    symbol: pair.baseToken?.symbol ?? "?",
    name: pair.baseToken?.name ?? "?",
    priceUsd: num(pair.priceUsd),
    score: Math.round(scored.score),
    components: scored.components,
    reasons: scored.reasons,
    warnings: scored.warnings,
    fdv: num(pair.fdv),
    liquidity: num(pair.liquidity?.usd),
    volH1: num(pair.volume?.h1),
    vol24h: num(pair.volume?.h24),
    ageHours,
    buySellRatio: buySellRatio(pair),
    pairUrl: pair.url ?? "",
    boosts,
    m5: num(pair.priceChange?.m5),
    h1: num(pair.priceChange?.h1),
    h6: num(pair.priceChange?.h6),
    h24: num(pair.priceChange?.h24),
    txns1h: num(t1h?.buys) + num(t1h?.sells),
    sizingKey,
  };
}

interface RugSummary {
  score?: number;
  risks?: { name?: string; level?: string }[];
}

/** Rugcheck top risky candidates; annotate warnings. Server hits rugcheck
 *  directly, client falls back to our proxy route. */
async function annotateRugcheck(
  signals: MemeSignal[],
  server: boolean
): Promise<void> {
  const targets = signals.slice(0, 10);
  await Promise.allSettled(
    targets.map(async (s) => {
      try {
        const url = server
          ? `https://api.rugcheck.xyz/v1/tokens/${s.address}/report/summary`
          : `/api/rugcheck?mint=${s.address}`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) return;
        const data: RugSummary = await res.json();
        const dangers = (data.risks ?? []).filter((r) => r.level === "danger");
        const warns = (data.risks ?? []).filter((r) => r.level === "warn");
        if (dangers.length) {
          s.warnings.unshift(
            `RUGCHECK DANGER: ${dangers.map((d) => d.name).filter(Boolean).slice(0, 2).join(", ")}`
          );
          s.riskLevel = "EXTREME";
        } else if (warns.length) {
          s.warnings.push(
            `Rugcheck flags: ${warns.map((w) => w.name).filter(Boolean).slice(0, 2).join(", ")}`
          );
        } else {
          s.reasons.push("Rugcheck: no major risks flagged");
        }
      } catch {
        /* rugcheck unreachable — say nothing rather than fake safety */
      }
    })
  );
}

/**
 * Full scan → the play ladder, safest to wildest:
 *   sure2x     "2x GRINDER"      established + deep liq + bounce (70+)
 *   recovery3x "3x RECOVERY"     deep-dip low-cap reversals (60+)
 *   momentum   "MOMENTUM RIDER"  already running, volume accelerating (65+)
 *   higherCap  "HIGHER-CAP"      $5M+ dips with sentiment intact (55+)
 *   launches   "NEW LAUNCH"      <24h with real liquidity (65+)
 *   degens     moonshot tiers    5x / 10x / 100x POTENTIAL (45+)
 */
export async function runMemeScan(
  opts: { server?: boolean } = {}
): Promise<MemeScanResult> {
  const tokens = await discoverTokens();
  const boostsMap = new Map(tokens.map((t) => [t.address, t.boosts]));
  const pairMap = await fetchPairsBatch(tokens.map((t) => t.address));

  const sure2x: MemeSignal[] = [];
  const recovery3x: MemeSignal[] = [];
  const momentum: MemeSignal[] = [];
  const higherCap: MemeSignal[] = [];
  const launches: MemeSignal[] = [];
  const degens: MemeSignal[] = [];
  const now = Date.now();

  // Pulse accumulators
  let analyzed = 0;
  let green = 0;
  let totalVol = 0;
  const h24s: number[] = [];

  pairMap.forEach((pairs, address) => {
    const pair = bestSolanaPair(pairs);
    if (!pair) return;
    const liq = num(pair.liquidity?.usd);
    const vol24 = num(pair.volume?.h24);
    if (liq < 3_000 || vol24 < 5_000) return; // dust filter

    const h24 = num(pair.priceChange?.h24);
    const h6 = num(pair.priceChange?.h6);
    const h1 = num(pair.priceChange?.h1);
    const m5 = num(pair.priceChange?.m5);
    analyzed++;
    if (h24 > 0) green++;
    totalVol += vol24;
    h24s.push(h24);

    const created = num(pair.pairCreatedAt);
    const ageHours = created > 0 ? (now - created) / 3_600_000 : -1;
    if (ageHours <= 0) return;
    const boosts = boostsMap.get(address) ?? 0;
    const fdv = num(pair.fdv);
    const volH1 = num(pair.volume?.h1);
    const inDip = h24 < -8 || h6 < -5;
    const bsr = buySellRatio(pair);

    // ── 1. New launches (<24h) ──────────────────────────────────────
    if (ageHours < 24) {
      const scored = scoreLaunch(pair, ageHours, boosts);
      if (scored.score >= LAUNCH_MIN) {
        launches.push(
          baseSignal(pair, "LAUNCH", "NEW LAUNCH", ageHours, boosts, scored, "10x RUNNER")
        );
      }
      return; // launches are their own universe
    }

    // ── 2. 2x GRINDER — highest-probability tier ────────────────────
    if (
      ageHours >= 14 * 24 &&
      fdv >= 500_000 &&
      fdv <= 25_000_000 &&
      liq >= 25_000 &&
      h24 > -35 &&
      inDip
    ) {
      const scored = scoreSure2x(pair, ageHours);
      if (scored.score >= SURE2X_MIN) {
        sure2x.push(
          baseSignal(pair, "SURE", "2x GRINDER", ageHours, boosts, scored, "A")
        );
        return;
      }
    }

    // ── 3. Higher-cap recovery ($5M+) ───────────────────────────────
    if (fdv >= HIGH_CAP_FDV && inDip && bsr >= 1.0) {
      const scored = scoreRecovery(pair, ageHours);
      if (scored.score >= 55) {
        higherCap.push(
          baseSignal(pair, "HIGHER-CAP", "HIGHER-CAP RECOVERY", ageHours, boosts, scored, "A")
        );
        return;
      }
    }

    // ── 4. Momentum riders ──────────────────────────────────────────
    const volAccelerating = volH1 > 0 && (volH1 * 24) > vol24 * 1.5;
    if (h1 > 8 && m5 > -1 && volAccelerating) {
      const scored = scoreMomentum(pair);
      if (scored.score >= MOMENTUM_MIN) {
        momentum.push(
          baseSignal(pair, "MOMENTUM", "MOMENTUM RIDER", ageHours, boosts, scored, "5x POTENTIAL")
        );
        return;
      }
    }

    // ── 5. 3x recovery — deep-dip low-cap reversals ─────────────────
    if (
      fdv < HIGH_CAP_FDV &&
      ageHours >= 3 * 24 &&
      (h24 <= -30 || h6 <= -25)
    ) {
      const scored = scoreRecovery(pair, ageHours);
      if (scored.score >= RECOVERY_MIN) {
        recovery3x.push(
          baseSignal(pair, "RECOVERY", "3x RECOVERY", ageHours, boosts, scored, "B")
        );
        return;
      }
    }

    // ── 6. Degen moonshots ──────────────────────────────────────────
    if (inDip) {
      const moon = computeMoonshot(pair);
      if (moon.total >= 45 && moon.tier !== "LOW POTENTIAL") {
        const sig = baseSignal(
          pair,
          "DEGEN",
          moon.tier,
          ageHours,
          boosts,
          {
            score: moon.total,
            components: moon.components,
            reasons: moon.reasons,
            warnings: moon.warnings,
          },
          moon.tier
        );
        sig.tier = moon.tier;
        sig.riskLevel = moon.riskLevel;
        degens.push(sig);
      }
    }
  });

  const byScore = (a: MemeSignal, b: MemeSignal) => b.score - a.score;
  sure2x.sort(byScore);
  recovery3x.sort(byScore);
  momentum.sort(byScore);
  higherCap.sort(byScore);
  launches.sort(byScore);
  degens.sort(byScore);

  h24s.sort((a, b) => a - b);
  const pulse: ScanPulse = {
    discovered: tokens.length,
    analyzed,
    greenPct: analyzed > 0 ? Math.round((green / analyzed) * 100) : 0,
    medianH24: h24s.length ? Number(h24s[Math.floor(h24s.length / 2)].toFixed(1)) : 0,
    totalVol24hUsd: totalVol,
  };

  const result: MemeScanResult = {
    pulse,
    sure2x: sure2x.slice(0, 8),
    recovery3x: recovery3x.slice(0, 8),
    momentum: momentum.slice(0, 8),
    higherCap: higherCap.slice(0, 6),
    launches: launches.slice(0, 8),
    degens: degens.slice(0, 10),
  };

  await annotateRugcheck(
    [...result.degens, ...result.launches],
    opts.server ?? false
  );
  return result;
}
