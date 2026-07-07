import type { DexPair, MemeSignal, ScoreComponent } from "@/types";
import { clamp } from "@/lib/utils";

// Surfacing thresholds — below these, the signal is noise.
export const LAUNCH_MIN = 65;
export const RECOVERY_MIN = 60;

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

function buySellRatio(pair: DexPair): number {
  let best = 0;
  for (const tf of ["m5", "h1"] as const) {
    const t = pair.txns?.[tf];
    const buys = num(t?.buys);
    const sells = num(t?.sells);
    if (sells > 0) best = Math.max(best, buys / sells);
    else if (buys > 5) best = Math.max(best, 3);
  }
  return best;
}

/**
 * Launch mode: tokens < 24h old.
 *
 * The original spec wants LP-lock status and holder distribution — those
 * require paid APIs. We score with what DexScreener actually returns and
 * show the breakdown, so the number is never mystery meat.
 */
export function scoreLaunch(
  pair: DexPair,
  ageHours: number,
  boosts: number
): { score: number; components: ScoreComponent[]; reasons: string[]; warnings: string[] } {
  const liq = num(pair.liquidity?.usd);
  const fdv = num(pair.fdv);
  const vol24 = num(pair.volume?.h24);
  const volH1 = num(pair.volume?.h1);
  const ratio = buySellRatio(pair);
  const reasons: string[] = [];
  const warnings: string[] = [];
  const components: ScoreComponent[] = [];

  // Liquidity floor (25)
  let liqScore: number;
  if (liq >= 50_000) liqScore = 100;
  else if (liq >= 25_000) liqScore = 80;
  else if (liq >= 10_000) liqScore = 60;
  else if (liq >= 5_000) liqScore = 30;
  else liqScore = 5;
  if (liq >= 25_000) reasons.push(`Serious liquidity: $${(liq / 1000).toFixed(0)}K`);
  if (liq < 10_000) warnings.push(`Thin liquidity ($${(liq / 1000).toFixed(1)}K) — slippage risk`);
  components.push({ name: "Initial liquidity", weightPct: 25, score: liqScore, detail: `$${(liq / 1000).toFixed(1)}K` });

  // Volume / FDV (25)
  const turn = fdv > 0 ? vol24 / fdv : 0;
  const turnScore = clamp((turn / 3) * 100);
  if (turn >= 2) reasons.push(`Volume ${turn.toFixed(1)}x market cap — real interest`);
  components.push({ name: "Volume / market cap", weightPct: 25, score: turnScore, detail: `${turn.toFixed(2)}x` });

  // Buy pressure (25)
  let bpScore: number;
  if (ratio >= 2.5) bpScore = 100;
  else if (ratio >= 1.8) bpScore = 80;
  else if (ratio >= 1.3) bpScore = 60;
  else if (ratio >= 1.0) bpScore = 40;
  else bpScore = 15;
  if (ratio >= 1.8) reasons.push(`Buyers in control (${ratio.toFixed(1)}x buys/sells)`);
  components.push({ name: "Buy/sell pressure", weightPct: 25, score: bpScore, detail: `${ratio.toFixed(1)}x` });

  // Age sweet spot (15): 2-12h ideal — survived the sniper window, still early
  let ageScore: number;
  if (ageHours < 1) {
    ageScore = 25;
    warnings.push("Under 1h old — peak rug window");
  } else if (ageHours < 2) ageScore = 60;
  else if (ageHours <= 12) ageScore = 100;
  else ageScore = 75;
  components.push({ name: "Age window", weightPct: 15, score: ageScore, detail: `${ageHours.toFixed(1)}h old` });

  // Boost visibility (10)
  const boostScore = boosts > 0 ? clamp(50 + boosts * 10) : 30;
  if (boosts > 0) reasons.push(`DexScreener boosted (${boosts})`);
  components.push({ name: "Paid visibility", weightPct: 10, score: boostScore, detail: boosts ? `${boosts} boosts` : "none" });

  // Exit-trap penalty
  let score = components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0);
  if (fdv > 0 && liq > 0 && liq / fdv < 0.02) {
    score -= 15;
    warnings.push(`Exit trap: liquidity only ${((liq / fdv) * 100).toFixed(1)}% of FDV`);
  }
  if (volH1 === 0) {
    score -= 10;
    warnings.push("No volume in the last hour");
  }

  warnings.push("New token, unaudited. LP-lock and holder data unavailable on free APIs — verify before sizing.");
  return { score: clamp(score), components, reasons, warnings };
}

/**
 * Recovery mode: tokens 7-90 days old in a deep drawdown showing life.
 * ATH data isn't in DexScreener's pair payload, so drawdown is measured
 * from 24h/6h moves — displayed as such.
 */
export function scoreRecovery(
  pair: DexPair,
  ageHours: number
): { score: number; components: ScoreComponent[]; reasons: string[]; warnings: string[] } {
  const h24 = num(pair.priceChange?.h24);
  const h6 = num(pair.priceChange?.h6);
  const m5 = num(pair.priceChange?.m5);
  const h1 = num(pair.priceChange?.h1);
  const vol24 = num(pair.volume?.h24);
  const volH1 = num(pair.volume?.h1);
  const liq = num(pair.liquidity?.usd);
  const fdv = num(pair.fdv);
  const ratio = buySellRatio(pair);
  const reasons: string[] = [];
  const warnings: string[] = [];
  const components: ScoreComponent[] = [];

  // Volume resurgence (30): hourly pace vs 24h average
  const resurgence = vol24 > 0 && volH1 > 0 ? (volH1 * 24) / vol24 : 0;
  let resScore: number;
  if (resurgence >= 3) resScore = 100;
  else if (resurgence >= 2) resScore = 80;
  else if (resurgence >= 1.5) resScore = 60;
  else if (resurgence >= 1) resScore = 40;
  else resScore = 15;
  if (resurgence >= 2) reasons.push(`Volume resurgence: ${resurgence.toFixed(1)}x the 24h pace`);
  components.push({ name: "Volume resurgence", weightPct: 30, score: resScore, detail: `${resurgence.toFixed(1)}x hourly vs 24h avg` });

  // Buy pressure shift (25)
  let bpScore: number;
  if (ratio >= 2) bpScore = 100;
  else if (ratio >= 1.5) bpScore = 75;
  else if (ratio >= 1.1) bpScore = 55;
  else bpScore = 20;
  if (ratio >= 1.5) reasons.push(`Sentiment shifting: ${ratio.toFixed(1)}x buys/sells`);
  components.push({ name: "Buy-side shift", weightPct: 25, score: bpScore, detail: `${ratio.toFixed(1)}x buys/sells` });

  // Bounce forming (25): short frames green against a red 24h
  let bounceScore = 20;
  if (m5 > 0 && h1 > 0 && h24 < -20) {
    bounceScore = 95;
    reasons.push(`Bounce forming: 5m ${m5 > 0 ? "+" : ""}${m5.toFixed(1)}%, 1h +${h1.toFixed(1)}% against ${h24.toFixed(0)}% 24h`);
  } else if (m5 > 0 && h24 < -15) bounceScore = 70;
  else if (h1 > 0 && h24 < -15) bounceScore = 55;
  components.push({ name: "Bounce structure", weightPct: 25, score: bounceScore, detail: `5m ${m5.toFixed(1)}% / 1h ${h1.toFixed(1)}% / 24h ${h24.toFixed(0)}%` });

  // Dip depth (20): deeper dip = bigger recovery potential (with volume)
  let dipScore: number;
  const worst = Math.min(h6, h24);
  if (worst < -50) dipScore = 100;
  else if (worst < -35) dipScore = 80;
  else if (worst < -20) dipScore = 60;
  else dipScore = 25;
  components.push({ name: "Drawdown depth", weightPct: 20, score: dipScore, detail: `${worst.toFixed(0)}% (worst of 6h/24h)` });

  let score = components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0);
  if (fdv > 0 && liq > 0 && liq / fdv < 0.02) {
    score -= 15;
    warnings.push(`Exit trap: liquidity only ${((liq / fdv) * 100).toFixed(1)}% of FDV`);
  }
  if (liq < 10_000) warnings.push(`Thin liquidity ($${(liq / 1000).toFixed(1)}K)`);
  warnings.push("Drawdown measured from 24h move, not ATH (not in free API). Catching knives is risky by definition.");

  return { score: clamp(score), components, reasons, warnings };
}
