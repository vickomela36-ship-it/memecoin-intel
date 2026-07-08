import type {
  DexPair,
  MemeScanResult,
  MemeSignal,
  NarrativeIntel,
  ScanPulse,
} from "@/types";
import { bestSolanaPair, discoverTokens, fetchPairsBatch } from "./fetchers";
import {
  LAUNCH_MIN,
  MOMENTUM_MIN,
  RECOVERY_MIN,
  SURE2X_MIN,
  VOLUME_MIN,
  scoreLaunch,
  scoreMomentum,
  scoreRecovery,
  scoreSure2x,
  scoreVolume,
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

function isPumpfun(pair: DexPair, address: string): boolean {
  if (address.toLowerCase().endsWith("pump")) return true;
  const dex = (pair.dexId ?? "").toLowerCase();
  return dex.includes("pump");
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
    // Deep-copy lists: a token can live in several sections and rugcheck
    // annotations must not leak across copies.
    components: scored.components.map((c) => ({ ...c })),
    reasons: [...scored.reasons],
    warnings: [...scored.warnings],
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

// ── Narrative (meta) detection ────────────────────────────────────────────

const NARRATIVES: { name: string; keys: string[] }[] = [
  { name: "AI / Agents", keys: ["ai", "gpt", "agent", "bot", "neural", "grok", "llm"] },
  { name: "Dogs", keys: ["dog", "doge", "shib", "inu", "pup", "wif", "bonk", "floki"] },
  { name: "Cats", keys: ["cat", "kitty", "meow", "paw", "kitten"] },
  { name: "Frogs / PEPE", keys: ["pepe", "frog", "toad", "kek"] },
  { name: "Politics / Celebs", keys: ["trump", "maga", "elon", "musk", "biden", "president", "kamala"] },
  { name: "Animals (other)", keys: ["bear", "bull", "ape", "monkey", "penguin", "hippo", "capybara", "moo", "chicken"] },
  { name: "Anime / Waifu", keys: ["anime", "waifu", "chan", "senpai", "neko"] },
  { name: "Food", keys: ["burger", "pizza", "taco", "banana", "coffee", "cheese"] },
  { name: "Moon / Degen culture", keys: ["moon", "chad", "wojak", "based", "gigachad", "degen", "pump"] },
];

function classifyNarrative(symbol: string, name: string): string | null {
  const text = `${symbol} ${name}`.toLowerCase();
  for (const n of NARRATIVES) {
    if (n.keys.some((k) => text.includes(k))) return n.name;
  }
  return null;
}

interface NarrativeAcc {
  h24s: number[];
  green: number;
  vol: number;
  tokens: { symbol: string; vol: number; h24: number }[];
}

function buildMetas(acc: Map<string, NarrativeAcc>): NarrativeIntel[] {
  const metas: NarrativeIntel[] = [];
  acc.forEach((a, name) => {
    if (a.tokens.length < 3 || a.vol < 100_000) return; // too thin to be a meta
    const sorted = [...a.h24s].sort((x, y) => x - y);
    metas.push({
      name,
      tokens: a.tokens.length,
      greenPct: Math.round((a.green / a.tokens.length) * 100),
      medianH24: Number(sorted[Math.floor(sorted.length / 2)].toFixed(1)),
      totalVolUsd: a.vol,
      topSymbols: a.tokens
        .sort((x, y) => y.vol - x.vol)
        .slice(0, 3)
        .map((t) => t.symbol),
    });
  });
  // Heat = breadth + median move, volume as tiebreaker
  return metas
    .sort(
      (a, b) =>
        b.greenPct / 2 + b.medianH24 - (a.greenPct / 2 + a.medianH24) ||
        b.totalVolUsd - a.totalVolUsd
    )
    .slice(0, 5);
}

// ── Rugcheck annotation ───────────────────────────────────────────────────

interface RugSummary {
  score?: number;
  risks?: { name?: string; level?: string }[];
}

/** Returns the set of addresses rugcheck marked DANGER. */
async function annotateRugcheck(
  signals: MemeSignal[],
  server: boolean
): Promise<Set<string>> {
  const dangers = new Set<string>();
  const seen = new Set<string>();
  const targets = signals.filter((s) => {
    if (seen.has(s.address)) return false;
    seen.add(s.address);
    return true;
  }).slice(0, 14);

  await Promise.allSettled(
    targets.map(async (s) => {
      try {
        const url = server
          ? `https://api.rugcheck.xyz/v1/tokens/${s.address}/report/summary`
          : `/api/rugcheck?mint=${s.address}`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) return;
        const data: RugSummary = await res.json();
        const danger = (data.risks ?? []).filter((r) => r.level === "danger");
        const warns = (data.risks ?? []).filter((r) => r.level === "warn");
        // Apply to EVERY copy of this token across sections
        const copies = signals.filter((x) => x.address === s.address);
        for (const c of copies) {
          if (danger.length) {
            c.warnings.unshift(
              `RUGCHECK DANGER: ${danger.map((d) => d.name).filter(Boolean).slice(0, 2).join(", ")}`
            );
            c.riskLevel = "EXTREME";
          } else if (warns.length) {
            c.warnings.push(
              `Rugcheck flags: ${warns.map((w) => w.name).filter(Boolean).slice(0, 2).join(", ")}`
            );
          } else {
            c.reasons.push("Rugcheck: no major risks flagged");
          }
        }
        if (danger.length) dangers.add(s.address);
      } catch {
        /* rugcheck unreachable — say nothing rather than fake safety */
      }
    })
  );
  return dangers;
}

/**
 * Full scan → the play board. Categories are INDEPENDENT: a token appears
 * in every section it qualifies for.
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
  const volumePlays: MemeSignal[] = [];
  const higherCap: MemeSignal[] = [];
  const pumpfun: MemeSignal[] = [];
  const launches: MemeSignal[] = [];
  const degens: MemeSignal[] = [];
  const now = Date.now();

  // Pulse + narrative accumulators
  let analyzed = 0;
  let green = 0;
  let totalVol = 0;
  const h24s: number[] = [];
  const narrAcc = new Map<string, NarrativeAcc>();

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

    // Narrative bucket
    const symbol = pair.baseToken?.symbol ?? "?";
    const narrative = classifyNarrative(symbol, pair.baseToken?.name ?? "");
    if (narrative) {
      const acc = narrAcc.get(narrative) ?? { h24s: [], green: 0, vol: 0, tokens: [] };
      acc.h24s.push(h24);
      if (h24 > 0) acc.green++;
      acc.vol += vol24;
      acc.tokens.push({ symbol, vol: vol24, h24 });
      narrAcc.set(narrative, acc);
    }

    const created = num(pair.pairCreatedAt);
    const ageHours = created > 0 ? (now - created) / 3_600_000 : -1;
    if (ageHours <= 0) return;
    const boosts = boostsMap.get(address) ?? 0;
    const fdv = num(pair.fdv);
    const volH1 = num(pair.volume?.h1);
    const inDip = h24 < -8 || h6 < -5;
    const bsr = buySellRatio(pair);
    const turnover = fdv > 0 ? vol24 / fdv : 0;
    const hourlyRatio = vol24 > 0 && volH1 > 0 ? (volH1 * 24) / vol24 : 0;

    // Every category evaluated independently — multi-section membership.

    // New launches (<24h)
    if (ageHours < 24) {
      const scored = scoreLaunch(pair, ageHours, boosts);
      if (scored.score >= LAUNCH_MIN) {
        launches.push(
          baseSignal(pair, "LAUNCH", "NEW LAUNCH", ageHours, boosts, scored, "10x RUNNER")
        );
      }
    }

    // Pump.fun releases (<48h, sentiment + momentum; security via rugcheck)
    if (
      isPumpfun(pair, address) &&
      ageHours < 48 &&
      bsr >= 1.2 &&
      h1 > 0 &&
      m5 > -2 &&
      liq >= 10_000
    ) {
      const scored = scoreLaunch(pair, Math.min(ageHours, 23), boosts);
      if (scored.score >= 65) {
        pumpfun.push(
          baseSignal(pair, "PUMPFUN", "PUMPFUN RELEASE", ageHours, boosts, scored, "10x RUNNER")
        );
      }
    }

    // 2x GRINDER
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
        sure2x.push(baseSignal(pair, "SURE", "2x GRINDER", ageHours, boosts, scored, "A"));
      }
    }

    // Higher-cap recovery
    if (fdv >= HIGH_CAP_FDV && inDip && bsr >= 1.0) {
      const scored = scoreRecovery(pair, ageHours);
      if (scored.score >= 55) {
        higherCap.push(
          baseSignal(pair, "HIGHER-CAP", "HIGHER-CAP RECOVERY", ageHours, boosts, scored, "A")
        );
      }
    }

    // Momentum riders
    const volAccelerating = volH1 > 0 && (volH1 * 24) > vol24 * 1.5;
    if (h1 > 8 && m5 > -1 && volAccelerating) {
      const scored = scoreMomentum(pair);
      if (scored.score >= MOMENTUM_MIN) {
        momentum.push(
          baseSignal(pair, "MOMENTUM", "MOMENTUM RIDER", ageHours, boosts, scored, "5x POTENTIAL")
        );
      }
    }

    // Volume plays — outsized turnover or accelerating pace on real volume
    if (vol24 >= 150_000 && (turnover >= 1 || hourlyRatio >= 2)) {
      const scored = scoreVolume(pair);
      if (scored.score >= VOLUME_MIN) {
        volumePlays.push(
          baseSignal(pair, "VOLUME", "VOLUME PLAY", ageHours, boosts, scored, "5x POTENTIAL")
        );
      }
    }

    // 3x recovery
    if (fdv < HIGH_CAP_FDV && ageHours >= 3 * 24 && (h24 <= -30 || h6 <= -25)) {
      const scored = scoreRecovery(pair, ageHours);
      if (scored.score >= RECOVERY_MIN) {
        recovery3x.push(
          baseSignal(pair, "RECOVERY", "3x RECOVERY", ageHours, boosts, scored, "B")
        );
      }
    }

    // Degen moonshots
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
  for (const list of [sure2x, recovery3x, momentum, volumePlays, higherCap, pumpfun, launches, degens]) {
    list.sort(byScore);
  }

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
    metas: buildMetas(narrAcc),
    sure2x: sure2x.slice(0, 8),
    recovery3x: recovery3x.slice(0, 8),
    momentum: momentum.slice(0, 8),
    volumePlays: volumePlays.slice(0, 8),
    higherCap: higherCap.slice(0, 6),
    pumpfun: pumpfun.slice(0, 8),
    launches: launches.slice(0, 8),
    degens: degens.slice(0, 10),
  };

  // Rugcheck: pumpfun releases and launches get priority (security gate),
  // then degens. DANGER-flagged tokens are REMOVED from the pumpfun section
  // ("passes enough security checks") but stay visible in degens, flagged.
  const dangers = await annotateRugcheck(
    [...result.pumpfun, ...result.launches, ...result.degens],
    opts.server ?? false
  );
  result.pumpfun = result.pumpfun.filter((s) => !dangers.has(s.address));

  return result;
}
