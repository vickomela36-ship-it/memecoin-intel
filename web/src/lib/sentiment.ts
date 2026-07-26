// Unified Sentiment engine — one explainable −100..+100 signal.
//
// Sentiment is built from ON-CHAIN FLOW only (buy/sell pressure, volume
// acceleration, transaction intensity). Price is deliberately NOT a component
// — price vs sentiment is where DIVERGENCE lives, the highest-value output.
// Velocity/acceleration are real: each token's score is tracked in a small
// localStorage ring buffer, so Δ and ΔΔ come from actual history, not guesses.

import { clamp } from "@/lib/utils";

export interface SentimentComponent {
  label: string;
  value: number; // the raw input, shown verbatim
  weight: number; // 0..1 contribution weight
  source: string;
}

export interface SentimentSignal {
  score: number; // -100..+100
  confidence: number; // 0..1, sample-size aware
  velocity: number; // Δscore since last observation
  acceleration: number; // Δvelocity — the early signal
  components: SentimentComponent[];
  divergence: "none" | "bullish" | "bearish";
  divergenceNote: string;
  staleAsOf: number;
}

/** Inputs any memecoin surface can supply. */
export interface SentimentInput {
  address: string;
  buySellRatio: number;
  volH1: number;
  vol24h: number;
  vol5m?: number;
  txns1h: number;
  m5: number;
  h1: number;
}

// ── Instantaneous score from on-chain flow ─────────────────────────────────

function flowScore(inp: SentimentInput): {
  score: number;
  components: SentimentComponent[];
} {
  const components: SentimentComponent[] = [];

  // Buy/sell pressure (40%) — 1.0 neutral, 2x ⇒ +60, 3x+ ⇒ +100, 0.5 ⇒ −60
  const bsr = inp.buySellRatio;
  const bpScore = bsr >= 1 ? Math.min(100, (bsr - 1) * 60) : Math.max(-100, (bsr - 1) * 120);
  components.push({ label: "Buy/sell pressure", value: Number(bsr.toFixed(2)), weight: 0.4, source: "DexScreener txns" });

  // Volume acceleration (35%) — hourly pace vs 24h avg, plus 5m burst
  const hourly = inp.vol24h > 0 && inp.volH1 > 0 ? (inp.volH1 * 24) / inp.vol24h : 1;
  const instant = inp.volH1 > 0 && inp.vol5m ? (inp.vol5m * 12) / inp.volH1 : hourly;
  const accel = Math.max(hourly, instant);
  const volScore = accel >= 1 ? Math.min(100, (accel - 1) * 55) : Math.max(-60, (accel - 1) * 60);
  components.push({ label: "Volume acceleration", value: Number(accel.toFixed(2)), weight: 0.35, source: "DexScreener volume" });

  // Transaction intensity (25%) — how much flow, a crowd proxy
  const t = inp.txns1h;
  const txScore = t >= 500 ? 100 : t >= 200 ? 70 : t >= 80 ? 45 : t >= 30 ? 20 : 0;
  components.push({ label: "Transaction intensity", value: t, weight: 0.25, source: "DexScreener txns (1h)" });

  const score = clamp(
    bpScore * 0.4 + volScore * 0.35 + txScore * 0.25,
    -100,
    100
  );
  return { score: Math.round(score), components };
}

/** Instantaneous score + confidence WITHOUT touching history — safe to call
 *  from logging paths that shouldn't perturb the velocity ring buffer. */
export function instantSentiment(inp: SentimentInput): { score: number; confidence: number } {
  return { score: flowScore(inp).score, confidence: confidenceFrom(inp.txns1h) };
}

/** Confidence scales with sample size — 3 txns ≠ 3,000. */
function confidenceFrom(txns1h: number): number {
  if (txns1h >= 1000) return 0.95;
  if (txns1h >= 300) return 0.85;
  if (txns1h >= 100) return 0.65;
  if (txns1h >= 30) return 0.4;
  return 0.2;
}

// ── Velocity / acceleration via a per-token ring buffer ────────────────────

interface Snap {
  t: number;
  score: number;
  vel: number;
}
const HIST_KEY = "mi_sentiment_hist_v1";

function readHist(): Record<string, Snap[]> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(HIST_KEY) ?? "{}");
  } catch {
    return {};
  }
}
function writeHist(h: Record<string, Snap[]>) {
  if (typeof window === "undefined") return;
  try {
    // Cap total tokens tracked to keep storage small
    const keys = Object.keys(h);
    if (keys.length > 200) for (const k of keys.slice(0, keys.length - 200)) delete h[k];
    window.localStorage.setItem(HIST_KEY, JSON.stringify(h));
  } catch {
    /* full */
  }
}

/** Record the new score, return velocity (Δscore) and acceleration (Δvelocity). */
function track(address: string, score: number): { velocity: number; acceleration: number } {
  const hist = readHist();
  const series = hist[address] ?? [];
  const prev = series[series.length - 1];
  // Only record a new point if >2 min since the last (avoid noise on re-renders)
  const now = Date.now();
  if (prev && now - prev.t < 120_000) {
    return { velocity: prev.vel, acceleration: 0 };
  }
  const velocity = prev ? score - prev.score : 0;
  const acceleration = prev ? velocity - prev.vel : 0;
  series.push({ t: now, score, vel: velocity });
  hist[address] = series.slice(-6);
  writeHist(hist);
  return { velocity, acceleration };
}

// ── Divergence: price vs sentiment ─────────────────────────────────────────

function divergenceOf(
  score: number,
  velocity: number,
  priceH1: number
): { divergence: SentimentSignal["divergence"]; note: string } {
  if (priceH1 > 3 && (score < 0 || velocity < -5)) {
    return {
      divergence: "bearish",
      note: "Price is rising but on-chain sentiment is weak/falling — possible distribution into strength.",
    };
  }
  if (priceH1 < -3 && (score > 15 || velocity > 5)) {
    return {
      divergence: "bullish",
      note: "Price is falling but buy-side flow is rising — possible accumulation into weakness.",
    };
  }
  return { divergence: "none", note: "Price and sentiment are aligned." };
}

/** The full pipeline: instantaneous score + tracked Δ/ΔΔ + divergence. */
export function computeSentiment(inp: SentimentInput): SentimentSignal {
  const { score, components } = flowScore(inp);
  const confidence = confidenceFrom(inp.txns1h);
  const { velocity, acceleration } = track(inp.address, score);
  const { divergence, note } = divergenceOf(score, velocity, inp.h1);
  return {
    score,
    confidence,
    velocity,
    acceleration,
    components,
    divergence,
    divergenceNote: note,
    staleAsOf: Date.now(),
  };
}
