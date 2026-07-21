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


// Surfacing thresholds for the newer play categories
export const SURE2X_MIN = 70;
export const MOMENTUM_MIN = 65;

/**
 * "2x GRINDER" — the highest-probability tier. Established token, deep
 * liquidity, buyers in control, volume resurging, bounce structure forming.
 * Sized biggest, targets smallest (1.5-2x). Nothing is ever "sure" — this
 * is the closest the market offers.
 */
export function scoreSure2x(
  pair: DexPair,
  ageHours: number
): { score: number; components: ScoreComponent[]; reasons: string[]; warnings: string[] } {
  const m5 = num(pair.priceChange?.m5);
  const h1 = num(pair.priceChange?.h1);
  const h24 = num(pair.priceChange?.h24);
  const vol24 = num(pair.volume?.h24);
  const volH1 = num(pair.volume?.h1);
  const liq = num(pair.liquidity?.usd);
  const fdv = num(pair.fdv);
  const ratio = buySellRatio(pair);
  const reasons: string[] = [];
  const warnings: string[] = [];
  const components: ScoreComponent[] = [];

  // Established age (15)
  const days = ageHours / 24;
  const ageScore = days > 60 ? 100 : days > 30 ? 80 : days > 14 ? 60 : 30;
  if (days > 30) reasons.push(`Established: ${days.toFixed(0)} days old, survived multiple cycles`);
  components.push({ name: "Track record (age)", weightPct: 15, score: ageScore, detail: `${days.toFixed(0)}d old` });

  // Liquidity depth (20)
  let liqScore: number;
  if (liq >= 100_000) liqScore = 100;
  else if (liq >= 50_000) liqScore = 80;
  else if (liq >= 25_000) liqScore = 60;
  else liqScore = 25;
  if (liq >= 50_000) reasons.push(`Deep liquidity $${(liq / 1000).toFixed(0)}K — clean entries and exits`);
  components.push({ name: "Liquidity depth", weightPct: 20, score: liqScore, detail: `$${(liq / 1000).toFixed(0)}K` });

  // Buy pressure (20)
  let bpScore: number;
  if (ratio >= 1.8) bpScore = 100;
  else if (ratio >= 1.4) bpScore = 75;
  else if (ratio >= 1.15) bpScore = 55;
  else if (ratio >= 1.0) bpScore = 40;
  else bpScore = 15;
  if (ratio >= 1.4) reasons.push(`Buyers in control (${ratio.toFixed(1)}x buys/sells)`);
  components.push({ name: "Buy pressure", weightPct: 20, score: bpScore, detail: `${ratio.toFixed(1)}x` });

  // Volume resurgence (25)
  const resurgence = vol24 > 0 && volH1 > 0 ? (volH1 * 24) / vol24 : 0;
  let resScore: number;
  if (resurgence >= 3) resScore = 100;
  else if (resurgence >= 2) resScore = 80;
  else if (resurgence >= 1.5) resScore = 60;
  else if (resurgence >= 1) resScore = 40;
  else resScore = 20;
  if (resurgence >= 2) reasons.push(`Volume resurgence ${resurgence.toFixed(1)}x the 24h pace`);
  components.push({ name: "Volume resurgence", weightPct: 25, score: resScore, detail: `${resurgence.toFixed(1)}x hourly vs 24h` });

  // Bounce structure (20)
  let bounce = 25;
  if (m5 > 0 && h1 > 0 && h24 < -10) {
    bounce = 95;
    reasons.push(`Bounce confirmed: 5m +${m5.toFixed(1)}% and 1h +${h1.toFixed(1)}% against ${h24.toFixed(0)}% 24h`);
  } else if (h1 > 0 && h24 < -10) bounce = 70;
  else if (m5 > 0) bounce = 50;
  components.push({ name: "Bounce structure", weightPct: 20, score: bounce, detail: `5m ${m5.toFixed(1)}% / 1h ${h1.toFixed(1)}% / 24h ${h24.toFixed(0)}%` });

  let score = components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0);
  if (fdv > 0 && liq > 0 && liq / fdv < 0.04) {
    score -= 10;
    warnings.push(`Liquidity is ${((liq / fdv) * 100).toFixed(1)}% of FDV — thinner than this tier demands`);
  }
  warnings.push('"Sure" does not exist — this is the highest-probability tier, not a guarantee. Target 1.5-2x, take profit.');

  return { score: clamp(score), components, reasons, warnings };
}

/**
 * "MOMENTUM RIDER" — already running with volume accelerating.
 * You ride these, you don't predict them. Chasing extended moves is
 * penalized: the freshness component scores how new the move is.
 */
export function scoreMomentum(
  pair: DexPair
): { score: number; components: ScoreComponent[]; reasons: string[]; warnings: string[] } {
  const m5 = num(pair.priceChange?.m5);
  const h1 = num(pair.priceChange?.h1);
  const h6 = num(pair.priceChange?.h6);
  const vol24 = num(pair.volume?.h24);
  const volH1 = num(pair.volume?.h1);
  const vol5m = num(pair.volume?.m5);
  const liq = num(pair.liquidity?.usd);
  const fdv = num(pair.fdv);
  const ratio = buySellRatio(pair);
  const reasons: string[] = [];
  const warnings: string[] = [];
  const components: ScoreComponent[] = [];

  // Momentum strength (30)
  let momo: number;
  if (h1 >= 30) momo = 100;
  else if (h1 >= 20) momo = 85;
  else if (h1 >= 12) momo = 70;
  else momo = 50;
  if (h1 >= 20) reasons.push(`Running hard: +${h1.toFixed(0)}% in the last hour`);
  components.push({ name: "Momentum strength", weightPct: 30, score: momo, detail: `1h +${h1.toFixed(1)}%` });

  // Volume acceleration (30)
  const hourlyRatio = vol24 > 0 && volH1 > 0 ? (volH1 * 24) / vol24 : 0;
  const instantRatio = volH1 > 0 && vol5m > 0 ? (vol5m * 12) / volH1 : 0;
  let volScore: number;
  if (instantRatio >= 2 && vol5m > 500) volScore = 100;
  else if (hourlyRatio >= 3) volScore = 85;
  else if (hourlyRatio >= 2) volScore = 70;
  else if (hourlyRatio >= 1.5) volScore = 50;
  else volScore = 25;
  if (instantRatio >= 2) reasons.push(`Volume accelerating NOW (${instantRatio.toFixed(1)}x 5m pace)`);
  components.push({ name: "Volume acceleration", weightPct: 30, score: volScore, detail: `${instantRatio.toFixed(1)}x instant / ${hourlyRatio.toFixed(1)}x hourly` });

  // Buy pressure (20)
  let bpScore: number;
  if (ratio >= 2) bpScore = 100;
  else if (ratio >= 1.5) bpScore = 75;
  else if (ratio >= 1.1) bpScore = 50;
  else bpScore = 20;
  components.push({ name: "Buy pressure", weightPct: 20, score: bpScore, detail: `${ratio.toFixed(1)}x buys/sells` });

  // Freshness of move (20) — h6 vs h1 tells you if you're early or chasing
  let fresh: number;
  if (h6 <= h1) {
    fresh = 90;
    reasons.push("Move just started — 1h gain exceeds the whole 6h move");
  } else if (h6 <= h1 * 2) fresh = 65;
  else {
    fresh = 30;
    warnings.push(`Extended move: +${h6.toFixed(0)}% over 6h — you are late, chase at your own risk`);
  }
  components.push({ name: "Move freshness", weightPct: 20, score: fresh, detail: `1h +${h1.toFixed(0)}% vs 6h +${h6.toFixed(0)}%` });

  let score = components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0);
  if (fdv > 0 && liq > 0 && liq / fdv < 0.02) {
    score -= 15;
    warnings.push(`Exit trap: liquidity only ${((liq / fdv) * 100).toFixed(1)}% of FDV`);
  }
  if (m5 < -3) {
    score -= 10;
    warnings.push(`5m turning red (${m5.toFixed(1)}%) — momentum may be stalling`);
  }
  warnings.push("Momentum plays reverse violently. Hard stop, no exceptions.");

  return { score: clamp(score), components, reasons, warnings };
}


export const VOLUME_MIN = 65;

/**
 * "VOLUME PLAY" — outsized turnover relative to market cap. Where volume
 * concentrates, moves follow. Direction-agnostic on its own, so buy
 * pressure and short-frame action decide whether it's worth taking.
 */
export function scoreVolume(
  pair: DexPair
): { score: number; components: ScoreComponent[]; reasons: string[]; warnings: string[] } {
  const vol24 = num(pair.volume?.h24);
  const volH1 = num(pair.volume?.h1);
  const liq = num(pair.liquidity?.usd);
  const fdv = num(pair.fdv);
  const ratio = buySellRatio(pair);
  const reasons: string[] = [];
  const warnings: string[] = [];
  const components: ScoreComponent[] = [];

  // Turnover: 24h volume vs market cap (35)
  const turnover = fdv > 0 ? vol24 / fdv : 0;
  let turnScore: number;
  if (turnover >= 3) turnScore = 100;
  else if (turnover >= 2) turnScore = 85;
  else if (turnover >= 1.5) turnScore = 70;
  else if (turnover >= 1) turnScore = 50;
  else turnScore = 25;
  if (turnover >= 2) reasons.push(`Turnover ${turnover.toFixed(1)}x market cap in 24h — the crowd is HERE`);
  components.push({ name: "Turnover (vol/mcap)", weightPct: 35, score: turnScore, detail: `${turnover.toFixed(2)}x` });

  // Hourly pace vs 24h average (30)
  const hourlyRatio = vol24 > 0 && volH1 > 0 ? (volH1 * 24) / vol24 : 0;
  let paceScore: number;
  if (hourlyRatio >= 3) paceScore = 100;
  else if (hourlyRatio >= 2) paceScore = 80;
  else if (hourlyRatio >= 1.5) paceScore = 60;
  else paceScore = 30;
  if (hourlyRatio >= 2) reasons.push(`Volume still building: ${hourlyRatio.toFixed(1)}x the 24h pace`);
  components.push({ name: "Hourly pace", weightPct: 30, score: paceScore, detail: `${hourlyRatio.toFixed(1)}x vs 24h avg` });

  // Buy pressure decides direction (20)
  let bpScore: number;
  if (ratio >= 1.8) bpScore = 100;
  else if (ratio >= 1.3) bpScore = 70;
  else if (ratio >= 1.0) bpScore = 45;
  else bpScore = 15;
  components.push({ name: "Buy pressure", weightPct: 20, score: bpScore, detail: `${ratio.toFixed(1)}x buys/sells` });

  // Liquidity floor (15)
  let liqScore: number;
  if (liq >= 50_000) liqScore = 90;
  else if (liq >= 20_000) liqScore = 70;
  else if (liq >= 10_000) liqScore = 45;
  else liqScore = 15;
  components.push({ name: "Liquidity", weightPct: 15, score: liqScore, detail: `$${(liq / 1000).toFixed(0)}K` });

  let score = components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0);
  if (ratio < 1.0) {
    score -= 10;
    warnings.push("Sellers dominate the volume — this churn may be distribution, not accumulation");
  }
  if (fdv > 0 && liq > 0 && liq / fdv < 0.02) {
    score -= 15;
    warnings.push(`Exit trap: liquidity only ${((liq / fdv) * 100).toFixed(1)}% of FDV`);
  }
  warnings.push("High volume cuts both ways. Confirm direction on the 5m before entry.");

  return { score: clamp(score), components, reasons, warnings };
}


export const HOT_MIN = 65;

/**
 * "HOT" — the sniper recipe from the memecoin guide, encoded exactly:
 * Solana, new pair (<72h), liquidity $10K+ (locked — rugcheck verifies),
 * market cap $200K–$1M sweet spot, with real attention (txns) and buyers
 * in control. These are the 20-40x hunting grounds; sized like moonshots.
 */
export function scoreHot(
  pair: DexPair,
  ageHours: number,
  boosts: number
): { score: number; components: ScoreComponent[]; reasons: string[]; warnings: string[] } {
  const liq = num(pair.liquidity?.usd);
  const fdv = num(pair.fdv);
  const t1h = pair.txns?.h1;
  const txns1h = num(t1h?.buys) + num(t1h?.sells);
  const ratio = buySellRatio(pair);
  const reasons: string[] = [];
  const warnings: string[] = [];
  const components: ScoreComponent[] = [];

  // Market-cap window (30): $200K–$1M is the guide's sweet spot
  let mcScore: number;
  if (fdv >= 200_000 && fdv <= 1_000_000) {
    mcScore = 100;
    reasons.push(`In the $200K–$1M mcap sweet spot ($${(fdv / 1000).toFixed(0)}K)`);
  } else if (fdv >= 100_000 && fdv < 200_000) mcScore = 70;
  else if (fdv > 1_000_000 && fdv <= 3_000_000) mcScore = 60;
  else mcScore = 25;
  components.push({ name: "Mcap window ($200K–$1M)", weightPct: 30, score: mcScore, detail: `$${(fdv / 1000).toFixed(0)}K` });

  // Liquidity floor (25): guide minimum $10K, more is better
  let liqScore: number;
  if (liq >= 50_000) liqScore = 100;
  else if (liq >= 25_000) liqScore = 85;
  else if (liq >= 10_000) liqScore = 70;
  else liqScore = 15;
  if (liq < 10_000) warnings.push("Below the guide's $10K liquidity floor");
  components.push({ name: "Liquidity ($10K+ floor)", weightPct: 25, score: liqScore, detail: `$${(liq / 1000).toFixed(1)}K` });

  // Age window (20): <72h, with 6-48h the balance of early-but-survived
  let ageScore: number;
  if (ageHours >= 6 && ageHours <= 48) ageScore = 100;
  else if (ageHours < 6) {
    ageScore = 70;
    warnings.push("Very fresh — sniper/rug window still open");
  } else ageScore = 75; // 48-72h
  components.push({ name: "Pair age (<72h)", weightPct: 20, score: ageScore, detail: `${ageHours.toFixed(1)}h` });

  // Attention (15): the "hit by multiple bots at once" proxy — live txns
  let attnScore: number;
  if (txns1h >= 300) { attnScore = 100; reasons.push(`${txns1h} txns in the last hour — real hype`); }
  else if (txns1h >= 150) attnScore = 75;
  else if (txns1h >= 75) attnScore = 50;
  else attnScore = 25;
  components.push({ name: "Attention (1h txns)", weightPct: 15, score: attnScore, detail: String(txns1h) });

  // Buy pressure (10)
  const bpScore = ratio >= 2 ? 100 : ratio >= 1.5 ? 75 : ratio >= 1.1 ? 55 : 20;
  if (ratio >= 1.5) reasons.push(`Buyers in control (${ratio.toFixed(1)}x)`);
  components.push({ name: "Buy pressure", weightPct: 10, score: bpScore, detail: `${ratio.toFixed(1)}x` });

  let score = components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0);
  if (fdv > 0 && liq > 0 && liq / fdv < 0.02) {
    score -= 15;
    warnings.push(`Exit trap: liquidity only ${((liq / fdv) * 100).toFixed(1)}% of FDV`);
  }
  warnings.push("HOT = early + informed, not safe. Rugcheck runs automatically; DANGER tokens are removed from this section.");

  return { score: clamp(score), components, reasons, warnings };
}
