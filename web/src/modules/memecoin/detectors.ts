// Phase 3 detectors — coin-type classifier, botted-chart pattern detection,
// narrative helpers. All pure functions over data we already fetch.

import type { DexPair } from "@/types";

// ── Coin-type classifier ──────────────────────────────────────────────────

export type CoinClass =
  | "pure meme"
  | "celebrity"
  | "team-launched"
  | "CTO"
  | "utility"
  | "ownership";

export interface CoinTypeResult {
  type: CoinClass;
  confidence: "low" | "medium" | "high";
  reason: string;
  horizon: string; // guidance the tool adapts per type
}

const CELEB = ["trump", "elon", "musk", "biden", "kanye", "andrew tate", "tate", "messi", "ronaldo", "president", "kamala", "obama"];
const UTILITY = ["ai", "agent", "protocol", "swap", "dex", "stake", "vault", "bot", "terminal", "network", "chain", "data", "oracle"];
const OWNERSHIP = ["dao", "fund", "treasury", "index", "holders", "revenue", "buyback"];

/**
 * Best-effort classification from name/ticker + market shape. Honest:
 * without socials we can't be certain, so confidence is graded and the
 * reason is always shown. Time-horizon guidance differs per type because
 * holding a meme like a utility (too long) or trading a utility like a meme
 * (too short) is exactly how the guide says people lose.
 */
export function classifyCoinType(pair: DexPair): CoinTypeResult {
  const text = `${pair.baseToken?.symbol ?? ""} ${pair.baseToken?.name ?? ""}`.toLowerCase();
  const ageHours = pair.pairCreatedAt ? (Date.now() - pair.pairCreatedAt) / 3_600_000 : 0;

  if (CELEB.some((k) => text.includes(k))) {
    return {
      type: "celebrity",
      confidence: "medium",
      reason: "Name references a public figure — lives and dies on that person's news cycle.",
      horizon: "Event-driven. Exit fast on the news, don't marry it.",
    };
  }
  if (OWNERSHIP.some((k) => text.includes(k))) {
    return {
      type: "ownership",
      confidence: "low",
      reason: "Name suggests revenue/treasury mechanics — verify the buyback/fee claim before trusting it.",
      horizon: "Longer hold IF the mechanic is real. Confirm on-chain, not from the name.",
    };
  }
  if (UTILITY.some((k) => text.includes(k))) {
    return {
      type: "utility",
      confidence: "low",
      reason: "Name implies a product — but most 'utility' memecoins never ship. Verify a working product exists.",
      horizon: "Weeks-to-months IF it ships. Traded like a meme, you'll sell the winner too early.",
    };
  }
  if (ageHours > 24 * 14) {
    return {
      type: "CTO",
      confidence: "low",
      reason: "Survived 2+ weeks — often a community takeover keeping an abandoned launch alive.",
      horizon: "Depends on community strength. Watch holder growth, not just price.",
    };
  }
  return {
    type: "pure meme",
    confidence: "high",
    reason: "No product, celebrity, or ownership signal — pure attention play.",
    horizon: "Fast. Attention fades; take profits into strength, don't hold for a story that doesn't exist.",
  };
}

// ── Botted-chart detection ────────────────────────────────────────────────

export type OHLCV = { o: number; h: number; l: number; c: number; v: number }[];

export interface BottedPattern {
  pattern: string;
  confidence: number; // 0-1
  explain: string;
  range: [number, number] | null; // candle index range
}

function stddev(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / xs.length);
}
function mean(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

/**
 * Detect manufactured charts. Real supply/demand is noisy; bots are regular.
 * Returns every pattern that fires with a confidence and a candle range.
 */
export function detectBottedChart(candles: OHLCV): BottedPattern[] {
  const out: BottedPattern[] = [];
  if (candles.length < 12) return out;

  const bodies = candles.map((c) => Math.abs(c.c - c.o));
  const vols = candles.map((c) => c.v);

  // 1. Uniform candles — abnormally low variance of body + volume over a window
  const W = Math.min(20, candles.length);
  const recent = candles.slice(-W);
  const rb = recent.map((c) => Math.abs(c.c - c.o));
  const rv = recent.map((c) => c.v);
  const bodyCv = mean(rb) > 0 ? stddev(rb) / mean(rb) : 1;
  const volCv = mean(rv) > 0 ? stddev(rv) / mean(rv) : 1;
  if (bodyCv < 0.35 && volCv < 0.45 && mean(rv) > 0) {
    out.push({
      pattern: "Uniform candles",
      confidence: Math.min(1, (0.35 - bodyCv) / 0.35 + (0.45 - volCv) / 0.45) / 2 + 0.4,
      explain: "A run of candles with near-identical bodies and volumes — real buyers and sellers don't produce this regularity. A bot is making the market.",
      range: [candles.length - W, candles.length - 1],
    });
  }

  // 2. Instant candle + bot buys — one giant early candle then mechanical follow
  const avgBody = mean(bodies) || 1;
  const earlyBig = candles.slice(0, 3).findIndex((c) => Math.abs(c.c - c.o) > avgBody * 6);
  if (earlyBig >= 0) {
    out.push({
      pattern: "Instant candle",
      confidence: 0.7,
      explain: "A single enormous candle at/near launch — usually a large dev buy — followed by mechanical buying. The chart was kick-started by one entity.",
      range: [earlyBig, Math.min(earlyBig + 1, candles.length - 1)],
    });
  }

  // 3. Only-huge-candles — most candles are outsized, little in between
  const bigCount = bodies.filter((b) => b > avgBody * 2).length;
  if (bigCount / candles.length > 0.5) {
    out.push({
      pattern: "Only huge candles",
      confidence: 0.6,
      explain: "The chart is almost all oversized candles with little in between — one entity is moving price in both directions, not a real market.",
      range: null,
    });
  }

  // 4. Staircase — repeated similar up-steps with flat consolidation between
  let steps = 0;
  for (let i = 2; i < candles.length; i++) {
    const up = candles[i].c > candles[i - 1].c * 1.05;
    const flatBefore = Math.abs(candles[i - 1].c - candles[i - 2].c) < candles[i - 2].c * 0.01;
    if (up && flatBefore) steps++;
  }
  if (steps >= 4) {
    out.push({
      pattern: "Staircase",
      confidence: Math.min(0.9, 0.4 + steps * 0.08),
      explain: `${steps} identical step-ups with flat consolidation between them at regular intervals — a bot walking the price up on a schedule.`,
      range: null,
    });
  }

  return out.sort((a, b) => b.confidence - a.confidence);
}

// ── Narrative collision ───────────────────────────────────────────────────

/** Extract the distinctive narrative keyword from a token's name/ticker. */
export function narrativeKeyword(symbol: string, name: string): string {
  const stop = new Set(["the", "coin", "token", "inu", "sol", "on", "of", "a", "official"]);
  const words = `${name}`.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 2 && !stop.has(w));
  return words[0] ?? symbol.toLowerCase();
}

export interface NarrativeCompetitor {
  symbol: string;
  address: string;
  ageHours: number;
  fdv: number;
  vol24: number;
  liq: number;
  isLeaderByVol: boolean;
  canonicalMatch: boolean; // ticker/name closely matches the searched keyword
}

export interface NarrativeCollision {
  keyword: string;
  competitors: NarrativeCompetitor[];
  vampRisk: boolean;
  vampReason: string;
}

/** Build a collision report from DexScreener search results for the keyword. */
export function buildCollision(
  keyword: string,
  self: { symbol: string; address: string },
  pairs: DexPair[]
): NarrativeCollision {
  const now = Date.now();
  const seen = new Set<string>();
  const competitors: NarrativeCompetitor[] = [];

  for (const p of pairs) {
    if (p.chainId !== "solana") continue;
    const addr = p.baseToken?.address;
    if (!addr || seen.has(addr)) continue;
    seen.add(addr);
    const sym = (p.baseToken?.symbol ?? "").toLowerCase();
    const nm = (p.baseToken?.name ?? "").toLowerCase();
    competitors.push({
      symbol: p.baseToken?.symbol ?? "?",
      address: addr,
      ageHours: p.pairCreatedAt ? (now - p.pairCreatedAt) / 3_600_000 : 0,
      fdv: Number(p.fdv) || 0,
      vol24: Number(p.volume?.h24) || 0,
      liq: Number(p.liquidity?.usd) || 0,
      isLeaderByVol: false,
      canonicalMatch: sym === keyword || nm === keyword,
    });
  }

  competitors.sort((a, b) => b.vol24 - a.vol24);
  if (competitors.length) competitors[0].isLeaderByVol = true;

  // Vamp risk: high volume but the leader's name doesn't canonically match
  // the narrative — a correctly-named coin can vamp it.
  const leader = competitors[0];
  const selfIsLeader = leader?.address === self.address;
  const vampRisk =
    !!leader &&
    leader.vol24 > 50_000 &&
    !leader.canonicalMatch &&
    competitors.some((c) => c.canonicalMatch && c.address !== leader.address);
  const vampReason = vampRisk
    ? `The volume leader ($${leader.symbol}) doesn't canonically match "${keyword}", but a correctly-named competitor exists. That's the exact setup where the leader gets vamped when the real name surfaces.`
    : selfIsLeader
      ? "This token is the current volume leader for its narrative."
      : "No obvious vamp mismatch detected.";

  return { keyword, competitors: competitors.slice(0, 8), vampRisk, vampReason };
}
