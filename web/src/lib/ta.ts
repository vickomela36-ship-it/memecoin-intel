// Market-structure + memecoin TA engine. Pure functions over OHLCV.
//
// Design notes that are load-bearing per the guide:
//  • Anchoring is BODY-TO-BODY by default. On low-liquidity memecoins a single
//    buyer creates a huge wick that represents one person, not the market, so
//    wick-anchored fibs are noise. The toggle is exposed and explained.
//  • Levels are only meaningful once price has reacted to them repeatedly over
//    days — so we SUPPRESS the fib/confluence overlay on very young coins and
//    say why, rather than drawing meaningless lines.
//  • Invalidation on memecoins is NOT a single candle close through a level —
//    they overshoot constantly via wicks/liquidity grabs. We require a retest
//    and rejection before calling a setup dead, and we say so.

export type Candle = { o: number; h: number; l: number; c: number; v: number };

export type TrendState =
  | "UPTREND"
  | "DOWNTREND"
  | "RANGING"
  | "REVERSAL FORMING";

export type AnchorMode = "body" | "wick";

export interface Swing {
  index: number;
  price: number;
  kind: "H" | "L";
}

export interface StructureResult {
  state: TrendState;
  detail: string;
  swings: Swing[];
  hh: boolean;
  hl: boolean;
  lh: boolean;
  ll: boolean;
  brokeUp: boolean;
  brokeDown: boolean;
}

export interface FibResult {
  drawn: boolean;
  reason: string;
  anchorMode: AnchorMode;
  low: number;
  high: number;
  direction: "up"; // memecoin fibs are drawn on the up-leg we're retracing into
  levels: { ratio: number; price: number; golden: boolean }[];
  goldenPocket: [number, number] | null; // [0.618, 0.65] price band
  inGoldenPocket: boolean;
}

export interface ConfluenceSignal {
  kind: "fib" | "prior S/R" | "round number" | "high-volume node";
  price: number;
  detail: string;
}

export interface ConfluenceResult {
  zonePrice: number;
  signals: ConfluenceSignal[];
  count: number;
  grade: "none" | "possible reaction" | "tradable area" | "high-confidence zone";
}

export interface InvalidationResult {
  level: number | null;
  basis: string;
  confirmed: boolean; // has price already retested-and-rejected below it?
  note: string;
}

export interface ChartAnalysis {
  usable: boolean;
  suppressReason: string | null;
  anchorMode: AnchorMode;
  structure: StructureResult;
  fib: FibResult | null;
  confluence: ConfluenceResult | null;
  invalidation: InvalidationResult | null;
  price: number;
}

// ── Swing detection ────────────────────────────────────────────────────────

/** Body extreme for a candle under the chosen anchor mode. */
function hi(c: Candle, mode: AnchorMode): number {
  return mode === "body" ? Math.max(c.o, c.c) : c.h;
}
function lo(c: Candle, mode: AnchorMode): number {
  return mode === "body" ? Math.min(c.o, c.c) : c.l;
}

/**
 * Fractal swing points over a k-bar window. A swing high is a bar whose body
 * high is the max of its neighborhood; a swing low likewise. Returns swings in
 * chronological order, tagged H/L.
 */
export function findSwings(
  candles: Candle[],
  mode: AnchorMode = "body",
  k = 2
): Swing[] {
  const swings: Swing[] = [];
  for (let i = k; i < candles.length - k; i++) {
    const win = candles.slice(i - k, i + k + 1);
    const bh = hi(candles[i], mode);
    const bl = lo(candles[i], mode);
    if (bh === Math.max(...win.map((c) => hi(c, mode)))) {
      swings.push({ index: i, price: bh, kind: "H" });
    }
    if (bl === Math.min(...win.map((c) => lo(c, mode)))) {
      swings.push({ index: i, price: bl, kind: "L" });
    }
  }
  return swings;
}

// ── Market structure ───────────────────────────────────────────────────────

export function marketStructure(
  candles: Candle[],
  mode: AnchorMode = "body"
): StructureResult {
  const empty: StructureResult = {
    state: "RANGING",
    detail: "not enough data to read structure",
    swings: [],
    hh: false,
    hl: false,
    lh: false,
    ll: false,
    brokeUp: false,
    brokeDown: false,
  };
  if (candles.length < 12) return empty;

  const swings = findSwings(candles, mode);
  const highs = swings.filter((s) => s.kind === "H");
  const lows = swings.filter((s) => s.kind === "L");
  if (highs.length < 2 || lows.length < 2) {
    return { ...empty, swings, detail: "no confirmed swing sequence yet" };
  }

  const [h1, h2] = highs.slice(-2);
  const [l1, l2] = lows.slice(-2);
  const hh = h2.price > h1.price;
  const hl = l2.price > l1.price;
  const lh = h2.price < h1.price;
  const ll = l2.price < l1.price;

  const lastClose = candles[candles.length - 1].c;
  const lastHigh = highs[highs.length - 1].price;
  const lastLow = lows[lows.length - 1].price;
  const brokeUp = lastClose > lastHigh;
  const brokeDown = lastClose < lastLow;

  let state: TrendState;
  let detail: string;
  if (lh && ll && brokeUp) {
    state = "REVERSAL FORMING";
    detail = "downtrend structure (LH+LL) just broke to the upside";
  } else if (hh && hl) {
    state = "UPTREND";
    detail = "higher highs + higher lows";
  } else if (lh && ll) {
    state = "DOWNTREND";
    detail = "lower highs + lower lows";
  } else {
    state = "RANGING";
    detail = "no clean higher-high / lower-low sequence — sideways";
  }

  return { state, detail, swings, hh, hl, lh, ll, brokeUp, brokeDown };
}

// ── Fibonacci auto-draw ────────────────────────────────────────────────────

const FIB_RATIOS = [0.5, 0.618, 0.786];

/**
 * Anchor from the most recent confirmed swing low to the swing high that
 * followed it (the up-leg we're retracing into). Suppressed when the chart is
 * ranging or the swing hasn't formed — we do not draw fibs on unformed swings
 * or inside a range.
 */
export function autoFib(
  candles: Candle[],
  structure: StructureResult,
  mode: AnchorMode = "body"
): FibResult {
  const price = candles[candles.length - 1]?.c ?? 0;
  const base: FibResult = {
    drawn: false,
    reason: "",
    anchorMode: mode,
    low: 0,
    high: 0,
    direction: "up",
    levels: [],
    goldenPocket: null,
    inGoldenPocket: false,
  };

  if (structure.state === "RANGING") {
    return { ...base, reason: "Chart is ranging — no completed swing to anchor a fib to. Suppressed." };
  }

  const highs = structure.swings.filter((s) => s.kind === "H");
  const lows = structure.swings.filter((s) => s.kind === "L");
  if (!highs.length || !lows.length) {
    return { ...base, reason: "Swing not yet formed — nothing to anchor. Suppressed." };
  }

  // Most recent swing high, and the most recent swing low that PRECEDES it.
  const swingHigh = highs[highs.length - 1];
  const priorLows = lows.filter((l) => l.index < swingHigh.index);
  if (!priorLows.length) {
    return { ...base, reason: "No swing low precedes the last swing high — swing incomplete. Suppressed." };
  }
  const swingLow = priorLows[priorLows.length - 1];
  const low = swingLow.price;
  const high = swingHigh.price;
  if (high <= low) {
    return { ...base, reason: "Degenerate swing (high ≤ low). Suppressed." };
  }

  const span = high - low;
  const levels = FIB_RATIOS.map((r) => ({
    ratio: r,
    // Retracement price measured DOWN from the high
    price: high - span * r,
    golden: r === 0.618,
  }));
  const gp618 = high - span * 0.618;
  const gp65 = high - span * 0.65;
  const goldenPocket: [number, number] = [Math.min(gp618, gp65), Math.max(gp618, gp65)];
  const inGoldenPocket = price >= goldenPocket[0] && price <= goldenPocket[1];

  return {
    drawn: true,
    reason:
      mode === "body"
        ? "Anchored body-to-body (ignoring wicks) — the memecoin-correct default: a lone wick is one buyer, not the market."
        : "Anchored wick-to-wick (standard TA). On thin memecoins this can be distorted by a single print.",
    anchorMode: mode,
    low,
    high,
    direction: "up",
    levels,
    goldenPocket,
    inGoldenPocket,
  };
}

// ── Confluence counter ─────────────────────────────────────────────────────

/** Nearest 1/2/5 × 10ⁿ "round" number to a price (works at memecoin scale). */
function nearestRound(price: number): number {
  if (price <= 0) return 0;
  const mag = Math.pow(10, Math.floor(Math.log10(price)));
  const candidates = [1, 2, 5, 10].map((m) => m * mag);
  return candidates.reduce((a, b) => (Math.abs(b - price) < Math.abs(a - price) ? b : a));
}

/** Price level where traded volume clustered most (a high-volume node). */
function highVolumeNode(candles: Candle[]): number | null {
  if (candles.length < 8) return null;
  const prices = candles.map((c) => (c.h + c.l + c.c) / 3);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  if (max <= min) return null;
  const BINS = 24;
  const vol = new Array(BINS).fill(0);
  candles.forEach((c, i) => {
    const b = Math.min(BINS - 1, Math.floor(((prices[i] - min) / (max - min)) * BINS));
    vol[b] += c.v;
  });
  let best = 0;
  for (let b = 1; b < BINS; b++) if (vol[b] > vol[best]) best = b;
  return min + ((best + 0.5) / BINS) * (max - min);
}

/**
 * Count independent signals landing near a target zone (default: the golden
 * pocket if we're in a retracement, else current price). Grade by count.
 */
export function confluence(
  candles: Candle[],
  structure: StructureResult,
  fib: FibResult | null
): ConfluenceResult {
  const price = candles[candles.length - 1]?.c ?? 0;
  const zonePrice = fib?.drawn ? (fib.goldenPocket![0] + fib.goldenPocket![1]) / 2 : price;
  const near = (a: number, b: number) => b > 0 && Math.abs(a - b) / b <= 0.03; // 3%

  const signals: ConfluenceSignal[] = [];

  // 1. Fib level in the zone
  if (fib?.drawn) {
    const hit = fib.levels.find((l) => near(l.price, zonePrice));
    if (hit) {
      signals.push({
        kind: "fib",
        price: hit.price,
        detail: `${(hit.ratio * 100).toFixed(1)}% retracement${hit.golden ? " (golden pocket)" : ""}`,
      });
    }
  }

  // 2. Prior swing support/resistance near the zone (excluding the anchor swing)
  const priorSR = structure.swings.find((s) => near(s.price, zonePrice));
  if (priorSR) {
    signals.push({
      kind: "prior S/R",
      price: priorSR.price,
      detail: `previous swing ${priorSR.kind === "H" ? "high (resistance)" : "low (support)"} price was tested here`,
    });
  }

  // 3. Round number near the zone
  const round = nearestRound(zonePrice);
  if (near(round, zonePrice)) {
    signals.push({ kind: "round number", price: round, detail: "psychological round-number level" });
  }

  // 4. High-volume node near the zone
  const hvn = highVolumeNode(candles);
  if (hvn !== null && near(hvn, zonePrice)) {
    signals.push({ kind: "high-volume node", price: hvn, detail: "most traded price — a lot of positions sit here" });
  }

  const count = signals.length;
  const grade =
    count >= 3 ? "high-confidence zone" : count === 2 ? "tradable area" : count === 1 ? "possible reaction" : "none";
  return { zonePrice, signals, count, grade };
}

// ── Invalidation (with memecoin retest nuance) ─────────────────────────────

export function invalidation(
  candles: Candle[],
  structure: StructureResult,
  fib: FibResult | null
): InvalidationResult {
  // Prefer the 0.786 level; fall back to the higher-low the fib was drawn from.
  let level: number | null = null;
  let basis = "";
  if (fib?.drawn) {
    const f786 = fib.levels.find((l) => l.ratio === 0.786);
    if (f786) {
      level = f786.price;
      basis = "a decisive close below the 0.786 retracement";
    } else {
      level = fib.low;
      basis = "a break of the swing low the fib was drawn from";
    }
  } else {
    const lows = structure.swings.filter((s) => s.kind === "L");
    if (lows.length) {
      level = lows[lows.length - 1].price;
      basis = "a break of the last higher-low";
    }
  }

  if (level === null) {
    return { level: null, basis: "no structure to anchor invalidation", confirmed: false, note: "Draw a swing first." };
  }

  // Memecoin nuance: a single close below isn't death. Look for a retest that
  // FAILED to reclaim — closed below, bounced back to the level, rejected.
  let confirmed = false;
  const recent = candles.slice(-12);
  const brokeIdx = recent.findIndex((c) => c.c < level!);
  if (brokeIdx >= 0) {
    const after = recent.slice(brokeIdx + 1);
    const reclaimedThenRejected =
      after.some((c) => c.h >= level! * 0.99) && after.every((c) => c.c < level! * 1.01);
    confirmed = reclaimedThenRejected;
  }

  return {
    level,
    basis,
    confirmed,
    note: confirmed
      ? "Already retested from below and rejected — this setup is invalidated, not just wicked."
      : "Requires confirmation: memecoins overshoot levels on wicks constantly. One close below is a liquidity grab; wait for a failed retest before calling it dead.",
  };
}

// ── Top-level: assemble the full chart read ────────────────────────────────

/**
 * Full analysis with the age gate applied. Very young coins have no levels
 * that price has reacted to repeatedly, so the fib/confluence overlay is
 * suppressed and the reason is surfaced — structure trend can still show with
 * a caveat.
 */
export function analyzeChart(
  candles: Candle[],
  ageHours: number,
  mode: AnchorMode = "body"
): ChartAnalysis {
  const price = candles[candles.length - 1]?.c ?? 0;
  const structure = marketStructure(candles, mode);

  // Age/history gate: need real days of reaction before levels mean anything.
  const tooYoung = ageHours > 0 && ageHours < 24;
  const tooFewBars = candles.length < 48; // ~12h of 15m candles
  if (tooYoung || tooFewBars) {
    return {
      usable: false,
      suppressReason:
        tooYoung
          ? `Coin is ${ageHours.toFixed(0)}h old — under a day. No price level has been tested repeatedly yet, so drawing fibs/levels would be fiction. Showing raw trend only.`
          : "Not enough price history yet for meaningful levels. Showing raw trend only.",
      anchorMode: mode,
      structure,
      fib: null,
      confluence: null,
      invalidation: null,
      price,
    };
  }

  const fib = autoFib(candles, structure, mode);
  const conf = confluence(candles, structure, fib.drawn ? fib : null);
  const inval = invalidation(candles, structure, fib.drawn ? fib : null);

  return {
    usable: true,
    suppressReason: null,
    anchorMode: mode,
    structure,
    fib,
    confluence: conf,
    invalidation: inval,
    price,
  };
}
