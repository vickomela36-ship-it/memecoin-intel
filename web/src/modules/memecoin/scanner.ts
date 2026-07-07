import type { DexPair, MemeScanResult, MemeSignal } from "@/types";
import { bestSolanaPair, discoverTokens, fetchPairsBatch } from "./fetchers";
import { LAUNCH_MIN, RECOVERY_MIN, scoreLaunch, scoreRecovery } from "./scoring";
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
  return {
    mode,
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
    sizingKey,
  };
}

function recoveryGrade(score: number): { grade: string; sizingKey: string } {
  if (score >= 80) return { grade: "A", sizingKey: "A" };
  if (score >= 70) return { grade: "B", sizingKey: "B" };
  return { grade: "C", sizingKey: "5x POTENTIAL" };
}

interface RugSummary {
  score?: number;
  risks?: { name?: string; level?: string }[];
}

/** Rugcheck the top degen candidates via our proxy; annotate warnings. */
async function annotateRugcheck(signals: MemeSignal[]): Promise<void> {
  const targets = signals.slice(0, 8);
  await Promise.allSettled(
    targets.map(async (s) => {
      try {
        const res = await fetch(`/api/rugcheck?mint=${s.address}`);
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
 * Full scan → four sections:
 *  - launches:   < 24h old, launch score 65+       (NEW LAUNCH gems)
 *  - recoveries: 7-90d low-cap (<$5M) drawdowns, 60+, graded A/B/C
 *  - higherCap:  $5M+ FDV dips with buy-side sentiment intact
 *  - degens:     moonshot-tiered risky plays (3x/5x/10x/100x)
 */
export async function runMemeScan(): Promise<MemeScanResult> {
  const tokens = await discoverTokens();
  const boostsMap = new Map(tokens.map((t) => [t.address, t.boosts]));
  const pairMap = await fetchPairsBatch(tokens.map((t) => t.address));

  const launches: MemeSignal[] = [];
  const recoveries: MemeSignal[] = [];
  const higherCap: MemeSignal[] = [];
  const degens: MemeSignal[] = [];
  const now = Date.now();

  pairMap.forEach((pairs, address) => {
    const pair = bestSolanaPair(pairs);
    if (!pair) return;
    const liq = num(pair.liquidity?.usd);
    const vol24 = num(pair.volume?.h24);
    if (liq < 3_000 || vol24 < 5_000) return; // dust filter

    const created = num(pair.pairCreatedAt);
    const ageHours = created > 0 ? (now - created) / 3_600_000 : -1;
    if (ageHours <= 0) return;
    const boosts = boostsMap.get(address) ?? 0;
    const fdv = num(pair.fdv);
    const h6 = num(pair.priceChange?.h6);
    const h24 = num(pair.priceChange?.h24);
    const inDip = h24 < -8 || h6 < -5;
    let surfaced = false;

    // ── New launches ────────────────────────────────────────────────
    if (ageHours < 24) {
      const scored = scoreLaunch(pair, ageHours, boosts);
      if (scored.score >= LAUNCH_MIN) {
        launches.push(
          baseSignal(pair, "LAUNCH", ageHours, boosts, scored, "10x RUNNER")
        );
        surfaced = true;
      }
    }

    // ── Higher-cap recovery ($5M+, sentiment intact) ────────────────
    if (!surfaced && fdv >= HIGH_CAP_FDV && inDip && buySellRatio(pair) >= 1.0) {
      const scored = scoreRecovery(pair, ageHours);
      if (scored.score >= 55) {
        const g = recoveryGrade(scored.score);
        const sig = baseSignal(pair, "HIGHER-CAP", ageHours, boosts, scored, "A");
        sig.grade = g.grade;
        higherCap.push(sig);
        surfaced = true;
      }
    }

    // ── Low-cap recovery (graded A/B/C) ─────────────────────────────
    if (
      !surfaced &&
      fdv < HIGH_CAP_FDV &&
      ageHours >= 7 * 24 &&
      ageHours <= 90 * 24 &&
      (h24 < -15 || h6 < -10)
    ) {
      const scored = scoreRecovery(pair, ageHours);
      if (scored.score >= RECOVERY_MIN) {
        const g = recoveryGrade(scored.score);
        const sig = baseSignal(pair, "RECOVERY", ageHours, boosts, scored, g.sizingKey);
        sig.grade = g.grade;
        recoveries.push(sig);
        surfaced = true;
      }
    }

    // ── Degen moonshot plays (risky gems) ───────────────────────────
    if (!surfaced && inDip) {
      const moon = computeMoonshot(pair);
      if (moon.total >= 45 && moon.tier !== "LOW POTENTIAL") {
        const sig = baseSignal(
          pair,
          "DEGEN",
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

  launches.sort((a, b) => b.score - a.score);
  recoveries.sort((a, b) => b.score - a.score);
  higherCap.sort((a, b) => b.score - a.score);
  degens.sort((a, b) => b.score - a.score);

  const result: MemeScanResult = {
    launches: launches.slice(0, 8),
    recoveries: recoveries.slice(0, 8),
    higherCap: higherCap.slice(0, 6),
    degens: degens.slice(0, 10),
    scanned: pairMap.size,
  };

  await annotateRugcheck(result.degens);
  return result;
}
