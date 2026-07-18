// Liquidity-provision call builder — classifies Meteora DLMM pools and
// attaches a concrete strategy (shape, bin step, range, entry, management)
// grounded in the Meteora LP framework. Pure functions.

import type { LpCall, LpClass, LpStrategy } from "@/types";

const STABLES = new Set(["USDC", "USDT", "PYUSD", "USDS", "USDE", "FDUSD", "DAI", "USDG", "UST"]);
const LSTS = new Set(["MSOL", "JITOSOL", "BSOL", "INF", "JUPSOL", "HSOL", "BNSOL", "LST", "JSOL", "COMPASSSOL"]);
const MAJORS = new Set(["SOL", "WSOL", "BTC", "WBTC", "CBBTC", "ETH", "WETH", "JUP", "JLP", "JTO", "RAY", "BONK", "WIF"]);

function tickers(name: string): [string, string] {
  const parts = (name || "").toUpperCase().split(/[-/]/);
  return [parts[0] ?? "", parts[1] ?? ""];
}

export function classifyPool(name: string): LpClass {
  const [x, y] = tickers(name);
  const bothStable = STABLES.has(x) && STABLES.has(y);
  const lstCorrelated =
    (LSTS.has(x) && (y === "SOL" || y === "WSOL")) ||
    (LSTS.has(y) && (x === "SOL" || x === "WSOL")) ||
    (LSTS.has(x) && LSTS.has(y));
  if (bothStable || lstCorrelated) return "STABLE";

  const isBig = (t: string) => MAJORS.has(t) || STABLES.has(t);
  if (isBig(x) && isBig(y)) return "BLUECHIP";
  return "MEMECOIN";
}

function binMatch(cls: LpClass, binStep: number): LpStrategy["binStepMatch"] {
  const bands: Record<LpClass, [number, number]> = {
    STABLE: [1, 8],
    BLUECHIP: [8, 30],
    MEMECOIN: [50, 200],
  };
  const [lo, hi] = bands[cls];
  if (binStep < lo) return "tighter than ideal";
  if (binStep > hi) return "wider than ideal";
  return "matched";
}

export function buildStrategy(cls: LpClass, binStep: number, name: string): LpStrategy {
  const [x, y] = tickers(name);
  const quote = y === "USDC" || y === "USDT" ? y : x === "USDC" || x === "USDT" ? x : "SOL";
  const match = binMatch(cls, binStep);

  if (cls === "STABLE") {
    return {
      shape: "Curve",
      binStepReco: "1–5 (base fee 0.01–0.05%)",
      binStepMatch: match,
      range: "Tight — ±0.3% around peg (a few bins each side)",
      sided: "Balanced deposit (auto-fill both tokens)",
      entry: "Add Liquidity → Curve shape → narrow range hugging the peg. Fees come from constant stable rotation.",
      manage: "Near set-and-forget. Only act if one side depegs.",
      ilNote: "IL near zero while both assets hold their peg — depeg is the real risk.",
    };
  }
  if (cls === "BLUECHIP") {
    return {
      shape: "Spot",
      binStepReco: "10–25 (base fee 0.1–0.25%)",
      binStepMatch: match,
      range: "Moderate — ±10–15% around current price",
      sided: "Balanced (auto-fill), or lean the side you'd rather accumulate",
      entry: "Add Liquidity → Spot shape → moderate range so you stay in-range through normal swings.",
      manage: "Check daily-ish. Rebalance/recenter if price drifts outside your range for long.",
      ilNote: "Moderate IL if the pair trends hard one way; dynamic fees partly offset it.",
    };
  }
  return {
    shape: "Bid-Ask",
    binStepReco: "50–150 (base fee 1–5%)",
    binStepMatch: match,
    range: "Wide/one-sided — set the bottom bin at your MAX acceptable drawdown",
    sided: `Single-sided ${quote} only (remove Auto-Fill) — dip-catcher entry`,
    entry: `Add Liquidity → Bid-Ask → supply ${quote} only → set bottom bin = the lowest price you'll absorb. Earns fees as price dips into range then pumps out.`,
    manage: "Active, cap ~1h/day. Take 5–10%/day profits. Cut if price closes below your bottom bin — don't hold a possible rug.",
    ilNote: "High IL + rug risk. Treat every position as time-sensitive; most memecoins trend to zero.",
  };
}

/** Quality score for ranking within a category. */
export function qualityScore(feeYieldDaily: number, volTvl: number, tvl: number, cls: LpClass): number {
  // Fee yield dominates; activity confirms it's real; TVL depth de-risks.
  const yieldPts = Math.min(50, feeYieldDaily * (cls === "STABLE" ? 800 : 300));
  const activityPts = Math.min(30, volTvl * (cls === "STABLE" ? 8 : 15));
  const depthPts = Math.min(20, Math.log10(Math.max(1, tvl)) * 4);
  return Math.round(yieldPts + activityPts + depthPts);
}

export interface RawPool {
  address: string;
  name: string;
  bin_step: number;
  base_fee_percentage: string | number;
  liquidity: string | number;
  trade_volume_24h: string | number;
  fees_24h: string | number;
  current_price: string | number;
  hide?: boolean;
  is_blacklisted?: boolean;
}

function n(v: unknown): number {
  const x = Number(v);
  return isFinite(x) ? x : 0;
}

export function buildLpCall(p: RawPool): LpCall | null {
  if (p.hide || p.is_blacklisted) return null;
  const tvl = n(p.liquidity);
  const vol = n(p.trade_volume_24h);
  const fees = n(p.fees_24h);
  if (tvl < 15_000 || vol < 15_000 || fees <= 0) return null;

  const cls = classifyPool(p.name);
  const feeYieldDaily = tvl > 0 ? fees / tvl : 0;
  const volTvl = tvl > 0 ? vol / tvl : 0;
  const binStep = n(p.bin_step);
  const strategy = buildStrategy(cls, binStep, p.name);

  const warnings: string[] = [];
  if (strategy.binStepMatch !== "matched") {
    warnings.push(
      `Pool bin step ${binStep} is ${strategy.binStepMatch} for a ${cls.toLowerCase()} pair (ideal ${strategy.binStepReco.split(" ")[0]}).`
    );
  }
  if (cls === "MEMECOIN") warnings.push("Memecoin LP: verify the token's safety first — LPing a rug still loses your capital.");
  if (feeYieldDaily > 0.05) warnings.push("Very high fee yield usually means very high volatility/IL — not free money.");

  return {
    address: p.address,
    name: p.name,
    cls,
    tvlUsd: tvl,
    vol24Usd: vol,
    fees24Usd: fees,
    feeYieldDailyPct: Number((feeYieldDaily * 100).toFixed(3)),
    estAprPct: Number((feeYieldDaily * 365 * 100).toFixed(0)),
    volTvlRatio: Number(volTvl.toFixed(2)),
    binStep,
    baseFeePct: n(p.base_fee_percentage),
    currentPrice: n(p.current_price),
    quality: qualityScore(feeYieldDaily, volTvl, tvl, cls),
    strategy,
    warnings,
    url: `https://app.meteora.ag/dlmm/${p.address}`,
  };
}
