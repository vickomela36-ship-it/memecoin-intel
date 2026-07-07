import type { DexPair, MemeSignal } from "@/types";
import {
  bestSolanaPair,
  discoverTokens,
  fetchPairsBatch,
} from "./fetchers";
import { LAUNCH_MIN, RECOVERY_MIN, scoreLaunch, scoreRecovery } from "./scoring";

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

function toSignal(
  pair: DexPair,
  mode: MemeSignal["mode"],
  ageHours: number,
  boosts: number,
  scored: {
    score: number;
    components: MemeSignal["components"];
    reasons: string[];
    warnings: string[];
  }
): MemeSignal {
  let ratio = 0;
  for (const tf of ["m5", "h1"] as const) {
    const t = pair.txns?.[tf];
    const buys = num(t?.buys);
    const sells = num(t?.sells);
    if (sells > 0) ratio = Math.max(ratio, buys / sells);
  }
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
    buySellRatio: ratio,
    pairUrl: pair.url ?? "",
    boosts,
  };
}

/** Full scan: discover → batch pair data → score both modes → threshold. */
export async function runMemeScan(): Promise<{
  launches: MemeSignal[];
  recoveries: MemeSignal[];
  scanned: number;
}> {
  const tokens = await discoverTokens();
  const boostsMap = new Map(tokens.map((t) => [t.address, t.boosts]));
  const pairMap = await fetchPairsBatch(tokens.map((t) => t.address));

  const launches: MemeSignal[] = [];
  const recoveries: MemeSignal[] = [];
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

    if (ageHours < 24) {
      const scored = scoreLaunch(pair, ageHours, boosts);
      if (scored.score >= LAUNCH_MIN) {
        launches.push(toSignal(pair, "LAUNCH", ageHours, boosts, scored));
      }
    } else if (ageHours >= 7 * 24 && ageHours <= 90 * 24) {
      const h24 = num(pair.priceChange?.h24);
      const h6 = num(pair.priceChange?.h6);
      if (h24 > -15 && h6 > -10) return; // not in a meaningful drawdown
      const scored = scoreRecovery(pair, ageHours);
      if (scored.score >= RECOVERY_MIN) {
        recoveries.push(toSignal(pair, "RECOVERY", ageHours, boosts, scored));
      }
    }
  });

  launches.sort((a, b) => b.score - a.score);
  recoveries.sort((a, b) => b.score - a.score);
  return {
    launches: launches.slice(0, 8),
    recoveries: recoveries.slice(0, 8),
    scanned: pairMap.size,
  };
}
