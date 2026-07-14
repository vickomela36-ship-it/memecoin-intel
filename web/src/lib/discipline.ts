// Discipline engine — state + friction logic. No buy/sell calls, ever.
// All persistence flows through this module so the localStorage backend
// can be swapped for KV sync in one place.

export type CoinType = "meme" | "utility" | "ownership";
export type Conviction = "LOW" | "MEDIUM" | "HIGH";
export type TraderType = "FISH" | "MONKEY";

export interface LadderLevel {
  mult: number; // price multiple vs entry
  sellPct: number; // % of position to sell at this level
  hit: boolean;
  hitAt: number | null;
  complied: boolean | null; // did the user actually sell when it hit?
}

export interface ReEval {
  at: number;
  wouldBuyUsd: number;
  positionValueUsd: number;
  suggestedSellUsd: number;
}

export interface ThesisVersion {
  at: number;
  why: string;
  invalidation: string;
}

export interface Position {
  id: string;
  symbol: string;
  address: string; // empty = no live price tracking
  coinType: CoinType;
  conviction: Conviction;
  why: string;
  invalidation: string;
  sizePct: number;
  sizeUsd: number;
  entryPrice: number; // 0 if unknown
  openedAt: number;
  ladder: LadderLevel[];
  reevals: ReEval[];
  thesisHistory: ThesisVersion[];
  status: "OPEN" | "CLOSED";
  closedAt: number | null;
  exitUsd: number | null;
  postMortem: { failure: string; rule: string } | null;
  lastPrice: number | null;
  peakValueUsd: number;
  roundtripAcked: boolean;
  stopAcked: boolean;
}

export interface DisciplineRule {
  text: string;
  maxSizePct: number | null; // structured guard: surfaced when about to break
  createdAt: number;
  fromSymbol: string;
}

export interface DisciplineProfile {
  portfolioUsd: number;
  lifeChangingUsd: number;
  traderType: TraderType | null;
  maxOpenPositions: number;
  /** Self-imposed lockout after a big loss. 0 = not opted in. Set while calm. */
  revengeLockoutMin: number;
  rules: DisciplineRule[];
  cooldownUntil: number;
}

export interface MissedTrade {
  symbol: string;
  kind: "found-early-didnt-buy" | "held-past-target" | "other";
  note: string;
  at: number;
}

export const DEFAULT_PROFILE: DisciplineProfile = {
  portfolioUsd: 0,
  lifeChangingUsd: 0,
  traderType: null,
  maxOpenPositions: 5,
  revengeLockoutMin: 0,
  rules: [],
  cooldownUntil: 0,
};

export const POST_MORTEM_FAILURES = [
  "Oversized for actual conviction",
  "No exit plan",
  "Ignored red flags I had already seen",
  "Emotional / FOMO entry",
  "Failed to act on new bearish information",
  "Held a launch thesis past its expiry",
  "Other",
];

/** Default ladders by coin type — set BEFORE entry, while calm. */
export const DEFAULT_LADDERS: Record<CoinType, LadderLevel[]> = {
  meme: [
    { mult: 2, sellPct: 50, hit: false, hitAt: null, complied: null },
    { mult: 4, sellPct: 25, hit: false, hitAt: null, complied: null },
  ],
  utility: [
    { mult: 1.5, sellPct: 30, hit: false, hitAt: null, complied: null },
    { mult: 3, sellPct: 30, hit: false, hitAt: null, complied: null },
  ],
  ownership: [{ mult: 2, sellPct: 25, hit: false, hitAt: null, complied: null }],
};

/** Sizing guideline (% of portfolio) by conviction, tuned by trader type. */
export function sizeGuidelinePct(
  conviction: Conviction,
  coinType: CoinType,
  traderType: TraderType | null
): number {
  let base = conviction === "HIGH" ? 10 : conviction === "MEDIUM" ? 5 : 2;
  if (coinType === "meme") base *= 0.8; // memes get less, whatever the conviction
  if (traderType === "FISH") base *= 0.8;
  if (traderType === "MONKEY") base *= 1.2;
  return Math.round(base * 10) / 10;
}

// ── Storage (swap point for KV sync later) ────────────────────────────────

const PROFILE_KEY = "mi_discipline_profile_v1";
const POSITIONS_KEY = "mi_positions_v1";
const MISSED_KEY = "mi_missed_trades_v1";

function read<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return Array.isArray(fallback)
      ? (parsed as T)
      : { ...fallback, ...parsed };
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* full */
  }
}

export function getProfile(): DisciplineProfile {
  return read(PROFILE_KEY, DEFAULT_PROFILE);
}
export function saveProfile(p: DisciplineProfile) {
  write(PROFILE_KEY, p);
}
export function getPositions(): Position[] {
  return read<Position[]>(POSITIONS_KEY, []);
}
export function savePositions(list: Position[]) {
  write(POSITIONS_KEY, list);
}
export function getMissed(): MissedTrade[] {
  return read<MissedTrade[]>(MISSED_KEY, []);
}
export function saveMissed(list: MissedTrade[]) {
  write(MISSED_KEY, list);
}

// ── Friction checks ───────────────────────────────────────────────────────

export interface EntryCheck {
  level: "block" | "warn";
  title: string;
  detail: string;
}

/**
 * Run every pre-entry check. The caller renders blocks as blocking modals
 * and warns as dismissible-with-acknowledgement. Never silently passes a
 * violated rule — the whole point is well-timed friction.
 */
export function checkEntry(args: {
  profile: DisciplineProfile;
  openPositions: Position[];
  closedPositions: Position[];
  draft: {
    sizePct: number;
    conviction: Conviction;
    coinType: CoinType;
    why: string;
    invalidation: string;
  };
  tokenH1?: number | null; // 1h price change if we could fetch it
}): EntryCheck[] {
  const { profile, openPositions, closedPositions, draft, tokenH1 } = args;
  const checks: EntryCheck[] = [];
  const now = Date.now();

  // Active cooldown (self-imposed, agreed to while calm)
  if (profile.cooldownUntil > now) {
    const mins = Math.ceil((profile.cooldownUntil - now) / 60000);
    checks.push({
      level: "block",
      title: "Cooldown active",
      detail: `You locked yourself out for ${mins} more minute(s). You agreed to this while calm — that person was thinking clearly.`,
    });
  }

  // User's own stored rules with structured guards
  for (const rule of profile.rules) {
    if (rule.maxSizePct !== null && draft.sizePct > rule.maxSizePct) {
      checks.push({
        level: "block",
        title: "Your own rule",
        detail: `After ${rule.fromSymbol}, you wrote: "${rule.text}" — this entry is ${draft.sizePct}% of portfolio, above your ${rule.maxSizePct}% limit.`,
      });
    }
  }

  // Gut check: if this goes to zero, can you trade normally tomorrow?
  const guideline = sizeGuidelinePct(draft.conviction, draft.coinType, profile.traderType);
  if (draft.sizePct > guideline * 2) {
    checks.push({
      level: "warn",
      title: "Size far above guideline",
      detail: `${draft.sizePct}% vs a ${guideline}% guideline for ${draft.conviction} conviction ${draft.coinType}. If this goes to zero, can you still trade normally tomorrow? If no, the size is too big.`,
    });
  }

  // Fish trading like a monkey (or vice versa)
  if (profile.traderType === "FISH" && draft.sizePct > guideline * 1.5) {
    checks.push({
      level: "warn",
      title: "Trading against your type",
      detail: `You identified as FISH (methodical, lower variance). This size is monkey behavior — fighting your own nature is where fish blow up.`,
    });
  }

  // Over-diversification
  if (openPositions.length >= profile.maxOpenPositions) {
    checks.push({
      level: "warn",
      title: "Too many open positions",
      detail: `${openPositions.length} open vs your ${profile.maxOpenPositions} max. Winners can't move the portfolio and the losers still add up.`,
    });
  }

  // FOMO: vertical entry
  if (tokenH1 !== null && tokenH1 !== undefined && tokenH1 > 40) {
    checks.push({
      level: "block",
      title: "FOMO gate: vertical chart",
      detail: `This token is +${tokenH1.toFixed(0)}% in the last hour. Would you be buying this right now if you had never seen the chart? Wait for the 5-minute cooldown, then decide.`,
    });
  }

  // FOMO: thesis quality
  if (draft.why.trim().length < 20 || draft.invalidation.trim().length < 10) {
    checks.push({
      level: "block",
      title: "Thesis too thin",
      detail: "If you can't articulate why you're buying and what would make you sell, that IS the answer.",
    });
  }

  // Revenge pattern: significant recent loss + fast/big re-entry
  const lastClosed = [...closedPositions].sort((a, b) => (b.closedAt ?? 0) - (a.closedAt ?? 0))[0];
  if (lastClosed && lastClosed.closedAt) {
    const lossPct =
      lastClosed.sizeUsd > 0 && lastClosed.exitUsd !== null
        ? (lastClosed.exitUsd - lastClosed.sizeUsd) / lastClosed.sizeUsd
        : 0;
    const minsSince = (now - lastClosed.closedAt) / 60000;
    const medianSize = medianSizePct(closedPositions) || draft.sizePct;
    if (lossPct < -0.3 && (minsSince < 30 || draft.sizePct > medianSize * 1.5)) {
      checks.push({
        level: profile.revengeLockoutMin > 0 ? "block" : "warn",
        title: "Revenge-trade pattern",
        detail:
          `You closed ${lastClosed.symbol} at ${(lossPct * 100).toFixed(0)}% ${minsSince < 60 ? `${Math.round(minsSince)} minutes ago` : "recently"}` +
          ` and you're now ${draft.sizePct > medianSize * 1.5 ? "sizing up" : "re-entering fast"}. ` +
          (profile.revengeLockoutMin > 0
            ? `Your pre-agreed ${profile.revengeLockoutMin}-minute lockout applies.`
            : "The market will still be here in an hour."),
      });
    }
  }

  return checks;
}

export function medianSizePct(positions: Position[]): number {
  const sizes = positions.map((p) => p.sizePct).filter((s) => s > 0).sort((a, b) => a - b);
  if (!sizes.length) return 0;
  return sizes[Math.floor(sizes.length / 2)];
}

/** Plan-adherence: of ladder levels that HIT, how many did the user honor? */
export function adherenceStat(positions: Position[]): { hit: number; complied: number } {
  let hit = 0;
  let complied = 0;
  for (const p of positions) {
    for (const l of p.ladder) {
      if (l.hit) {
        hit++;
        if (l.complied) complied++;
      }
    }
  }
  return { hit, complied };
}

/** Update live prices onto open positions; mark ladder hits + peaks. */
export function applyPrices(prices: Map<string, number>): Position[] {
  const list = getPositions();
  let changed = false;
  const now = Date.now();
  for (const p of list) {
    if (p.status !== "OPEN" || !p.address) continue;
    const price = prices.get(p.address);
    if (!price || price <= 0) continue;
    p.lastPrice = price;
    if (p.entryPrice > 0) {
      const value = p.sizeUsd * (price / p.entryPrice);
      if (value > p.peakValueUsd) p.peakValueUsd = value;
      for (const l of p.ladder) {
        if (!l.hit && price >= p.entryPrice * l.mult) {
          l.hit = true;
          l.hitAt = now;
        }
      }
    }
    changed = true;
  }
  if (changed) savePositions(list);
  return list;
}
