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

  // 2. Instant candle + bot buys — one giant early candle THEN mechanical
  //    follow-through. We now actually MEASURE the follow-through (regularity
  //    of the next candles) rather than asserting it: a big dev buy alone is
  //    weaker signal than a big buy followed by bot-regular buying.
  const avgBody = mean(bodies) || 1;
  const earlyBig = candles.slice(0, 3).findIndex((c) => Math.abs(c.c - c.o) > avgBody * 6);
  if (earlyBig >= 0) {
    const follow = candles.slice(earlyBig + 1, earlyBig + 8);
    const fb = follow.map((c) => Math.abs(c.c - c.o));
    const followCv = follow.length >= 4 && mean(fb) > 0 ? stddev(fb) / mean(fb) : 1;
    // Green, low-variance follow-through = mechanical buying by a bot.
    const upFollow = follow.filter((c) => c.c >= c.o).length;
    const mechanical = follow.length >= 4 && followCv < 0.5 && upFollow / follow.length >= 0.7;
    out.push({
      pattern: "Instant candle",
      confidence: mechanical ? 0.85 : 0.55,
      explain: mechanical
        ? "A single enormous candle at/near launch (a large dev buy) FOLLOWED by low-variance, mostly-green candles — measured mechanical buying. The chart was kick-started and is being walked up by one entity."
        : "A single enormous candle at/near launch — usually a large dev buy. The follow-through looks organic rather than botted, so treat this as concentration risk, not a confirmed bot chart.",
      range: [earlyBig, Math.min(earlyBig + follow.length, candles.length - 1)],
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

  // 4. Staircase — repeated up-steps with flat consolidation between. We now
  //    also verify the steps are EVENLY SPACED (low variance in the gap between
  //    consecutive steps): regular spacing is a bot on a schedule; irregular
  //    spacing is just a trending chart and shouldn't fire as strongly.
  const stepIdx: number[] = [];
  for (let i = 2; i < candles.length; i++) {
    const up = candles[i].c > candles[i - 1].c * 1.05;
    const flatBefore = Math.abs(candles[i - 1].c - candles[i - 2].c) < candles[i - 2].c * 0.01;
    if (up && flatBefore) stepIdx.push(i);
  }
  if (stepIdx.length >= 4) {
    const gaps: number[] = [];
    for (let i = 1; i < stepIdx.length; i++) gaps.push(stepIdx[i] - stepIdx[i - 1]);
    const gapCv = mean(gaps) > 0 ? stddev(gaps) / mean(gaps) : 1;
    const regular = gapCv < 0.4; // evenly spaced
    out.push({
      pattern: "Staircase",
      confidence: regular ? Math.min(0.9, 0.45 + stepIdx.length * 0.08) : Math.min(0.6, 0.3 + stepIdx.length * 0.05),
      explain: regular
        ? `${stepIdx.length} step-ups with flat consolidation between them at EVENLY SPACED intervals (gap variance ${(gapCv * 100).toFixed(0)}%) — a bot walking the price up on a schedule.`
        : `${stepIdx.length} step-ups with flat pauses, but the spacing is irregular — could be an ordinary trending chart rather than a scheduled bot. Weight lightly.`,
      range: [stepIdx[0], stepIdx[stepIdx.length - 1]],
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
  // Canonical-leader score — three independent factors, each 0..100.
  identity: number; // does the name/ticker actually match the subject?
  moat: number; // distribution moat: share of the narrative's volume + liquidity
  gravity: number; // product gravity: recurring mechanics beyond attention
  leaderScore: number; // weighted composite 0..100
  leaderNote: string;
}

export interface NarrativeCollision {
  keyword: string;
  competitors: NarrativeCompetitor[];
  vampRisk: boolean;
  vampReason: string;
}

/** Product-gravity proxy from the coin-type classification (0..100). Recurring
 *  mechanics (ownership/utility) give a reason to hold beyond attention. */
function gravityFor(cls: CoinClass): number {
  switch (cls) {
    case "ownership": return 80;
    case "utility": return 60;
    case "CTO": return 45;
    case "celebrity": return 30;
    default: return 20; // pure meme / team-launched: attention only
  }
}

/** Build a collision report from DexScreener search results for the keyword. */
export function buildCollision(
  keyword: string,
  self: { symbol: string; address: string },
  pairs: DexPair[]
): NarrativeCollision {
  const now = Date.now();
  const seen = new Set<string>();
  const raw: { c: NarrativeCompetitor; pair: DexPair; partial: boolean }[] = [];

  for (const p of pairs) {
    if (p.chainId !== "solana") continue;
    const addr = p.baseToken?.address;
    if (!addr || seen.has(addr)) continue;
    seen.add(addr);
    const sym = (p.baseToken?.symbol ?? "").toLowerCase();
    const nm = (p.baseToken?.name ?? "").toLowerCase();
    const exact = sym === keyword || nm === keyword;
    const partial = !exact && (sym.includes(keyword) || nm.includes(keyword));
    raw.push({
      pair: p,
      partial,
      c: {
        symbol: p.baseToken?.symbol ?? "?",
        address: addr,
        ageHours: p.pairCreatedAt ? (now - p.pairCreatedAt) / 3_600_000 : 0,
        fdv: Number(p.fdv) || 0,
        vol24: Number(p.volume?.h24) || 0,
        liq: Number(p.liquidity?.usd) || 0,
        isLeaderByVol: false,
        canonicalMatch: exact,
        identity: 0,
        moat: 0,
        gravity: 0,
        leaderScore: 0,
        leaderNote: "",
      },
    });
  }

  raw.sort((a, b) => b.c.vol24 - a.c.vol24);
  if (raw.length) raw[0].c.isLeaderByVol = true;
  const totalVol = raw.reduce((s, r) => s + r.c.vol24, 0) || 1;

  // Score each competitor on three independent factors.
  for (const { c, pair, partial } of raw) {
    // 1. Canonical identity — exact name/ticker match beats a partial beats none.
    c.identity = c.canonicalMatch ? 100 : partial ? 50 : 0;
    // 2. Distribution moat — share of the narrative's volume (0..70) + liquidity depth (0..30).
    const volShare = (c.vol24 / totalVol) * 70;
    const liqDepth = Math.min(30, (c.liq / 50_000) * 30);
    c.moat = Math.round(Math.min(100, volShare + liqDepth));
    // 3. Product gravity — a reason to hold beyond attention. Blends the
    //    coin-type signal (name) with REAL on-chain stickiness: deep liquidity
    //    and having survived (age), both of which outlast a pure attention pop.
    const gravBase = gravityFor(classifyCoinType(pair).type); // 0..80
    const liqBonus = Math.min(15, (c.liq / 100_000) * 15); // deep liquidity = stickiness
    const ageBonus = Math.min(15, (c.ageHours / (24 * 7)) * 15); // survived a week
    c.gravity = Math.round(Math.min(100, gravBase * 0.7 + liqBonus + ageBonus));
    c.leaderScore = Math.round(0.4 * c.identity + 0.35 * c.moat + 0.25 * c.gravity);
    c.leaderNote = `identity ${c.identity} · moat ${c.moat} · gravity ${c.gravity}`;
  }

  const competitors = raw.map((r) => r.c);
  const leader = competitors[0];
  const selfIsLeader = leader?.address === self.address;

  // The strongest CANONICAL contender — the coin that would win if the
  // narrative resolved to its true name.
  const canonicalContender = [...competitors]
    .filter((c) => c.identity >= 50)
    .sort((a, b) => b.leaderScore - a.leaderScore)[0];

  // Vamp risk: the volume leader has weak canonical identity but a
  // higher-identity competitor exists — the classic vamp setup.
  const vampRisk =
    !!leader &&
    leader.vol24 > 50_000 &&
    leader.identity < 100 &&
    !!canonicalContender &&
    canonicalContender.address !== leader.address;
  const vampReason = vampRisk
    ? `The volume leader ($${leader.symbol}, leader-score ${leader.leaderScore}) scores low on canonical identity, but $${canonicalContender!.symbol} matches the real name (score ${canonicalContender!.leaderScore}). That's the exact setup where the leader gets vamped when the true name surfaces.`
    : selfIsLeader
      ? `This token is the current volume leader for its narrative (leader-score ${leader.leaderScore}).`
      : leader
        ? `Volume leader $${leader.symbol} also holds the strongest canonical identity — no obvious vamp mismatch.`
        : "No competing tokens found for this narrative.";

  return { keyword, competitors: competitors.slice(0, 8), vampRisk, vampReason };
}

// ── Narrative word-frequency miner ─────────────────────────────────────────

const NARRATIVE_STOP = new Set([
  "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "her", "was", "one",
  "our", "out", "day", "get", "has", "him", "his", "how", "man", "new", "now", "old", "see",
  "two", "way", "who", "boy", "did", "its", "let", "put", "say", "she", "too", "use", "that",
  "this", "with", "have", "from", "they", "will", "your", "what", "when", "just", "into", "than",
  "then", "them", "some", "more", "over", "such", "only", "also", "back", "were", "been", "like",
  "coin", "token", "solana", "crypto", "memecoin", "launch", "https", "http", "www", "com",
]);

export interface MinedWord {
  word: string;
  count: number;
  share: number; // fraction of distinctive words
}

/**
 * Extract the most-repeated distinctive words from a block of discourse (an
 * announcement, article, thread, or set of posts). The pattern this catches:
 * a chain launches, every article repeats the word "trillions", and a
 * $TRILLIONS token runs on nothing but that word. Pure text analysis — the
 * caller supplies the corpus, so nothing is fabricated.
 */
export function mineNarrativeWords(text: string, topN = 6): MinedWord[] {
  const words = text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length >= 3 && w.length <= 20 && !NARRATIVE_STOP.has(w) && !/^\d+$/.test(w));
  if (!words.length) return [];
  const freq = new Map<string, number>();
  for (const w of words) freq.set(w, (freq.get(w) ?? 0) + 1);
  const total = words.length;
  return Array.from(freq.entries())
    .map(([word, count]) => ({ word, count, share: count / total }))
    .filter((w) => w.count >= 2) // must actually repeat
    .sort((a, b) => b.count - a.count)
    .slice(0, topN);
}
