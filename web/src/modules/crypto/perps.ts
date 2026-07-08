// Perp Desk engine — positioning data with a two-exchange fallback:
// Binance first, Bybit if Binance is blocked/unreachable in your region.
// Called CLIENT-SIDE on purpose: both exchanges geo-block datacenter IPs
// (where Vercel functions run) but allow browser CORS.

import type { PerpComponent, PerpTicket, WhalePrints } from "@/types";

const BINANCE = "https://fapi.binance.com";
const BYBIT = "https://api.bybit.com";

export const PERP_SYMBOLS: { symbol: string; display: string }[] = [
  { symbol: "BTCUSDT", display: "BTC" },
  { symbol: "ETHUSDT", display: "ETH" },
  { symbol: "SOLUSDT", display: "SOL" },
  { symbol: "DOGEUSDT", display: "DOGE" },
  { symbol: "1000PEPEUSDT", display: "PEPE" },
  { symbol: "WIFUSDT", display: "WIF" },
];

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Raw market snapshot (exchange-agnostic) ───────────────────────────────

interface RawPerp {
  source: "Binance" | "Bybit";
  mark: number;
  change24h: number;
  fundingPct8h: number;
  nextFundingMs: number;
  klines1h: number[][]; // [ts, open, high, low, close] chronological
  closes4h: number[];
  oiChange24hPct: number | null;
  lsRatio: number | null;
  takerAvg: number | null;
}

async function fetchBinance(symbol: string): Promise<RawPerp> {
  const [premium, ticker, k1h, k4h, oiHist, lsRatio, taker] =
    await Promise.allSettled([
      get<{ markPrice: string; lastFundingRate: string; nextFundingTime: number }>(
        `${BINANCE}/fapi/v1/premiumIndex?symbol=${symbol}`
      ),
      get<{ priceChangePercent: string }>(
        `${BINANCE}/fapi/v1/ticker/24hr?symbol=${symbol}`
      ),
      get<unknown[][]>(`${BINANCE}/fapi/v1/klines?symbol=${symbol}&interval=1h&limit=100`),
      get<unknown[][]>(`${BINANCE}/fapi/v1/klines?symbol=${symbol}&interval=4h&limit=60`),
      get<{ sumOpenInterestValue: string }[]>(
        `${BINANCE}/futures/data/openInterestHist?symbol=${symbol}&period=1h&limit=25`
      ),
      get<{ longShortRatio: string }[]>(
        `${BINANCE}/futures/data/globalLongShortAccountRatio?symbol=${symbol}&period=1h&limit=1`
      ),
      get<{ buySellRatio: string }[]>(
        `${BINANCE}/futures/data/takerlongshortRatio?symbol=${symbol}&period=1h&limit=6`
      ),
    ]);

  // Mark price and klines are mandatory — everything else degrades gracefully
  if (premium.status !== "fulfilled" || k1h.status !== "fulfilled") {
    throw new Error("binance core data unavailable");
  }

  let oi: number | null = null;
  if (oiHist.status === "fulfilled" && oiHist.value.length >= 24) {
    const now = num(oiHist.value[oiHist.value.length - 1].sumOpenInterestValue);
    const then = num(oiHist.value[0].sumOpenInterestValue);
    if (then > 0) oi = ((now - then) / then) * 100;
  }

  let taperAvg: number | null = null;
  if (taker.status === "fulfilled" && taker.value.length) {
    taperAvg =
      taker.value.reduce((a, t) => a + num(t.buySellRatio), 0) /
      taker.value.length;
  }

  return {
    source: "Binance",
    mark: num(premium.value.markPrice),
    change24h: ticker.status === "fulfilled" ? num(ticker.value.priceChangePercent) : 0,
    fundingPct8h: num(premium.value.lastFundingRate) * 100,
    nextFundingMs: num(premium.value.nextFundingTime),
    klines1h: k1h.value.map((c) => [num(c[0]), num(c[1]), num(c[2]), num(c[3]), num(c[4])]),
    closes4h: k4h.status === "fulfilled" ? k4h.value.map((c) => num(c[4])) : [],
    oiChange24hPct: oi,
    lsRatio:
      lsRatio.status === "fulfilled" && lsRatio.value.length
        ? num(lsRatio.value[0].longShortRatio)
        : null,
    takerAvg: taperAvg,
  };
}

interface BybitList<T> {
  retCode: number;
  result: { list: T[] };
}

async function fetchBybit(symbol: string): Promise<RawPerp> {
  const [tickers, k1h, k4h, oiHist, ratio] = await Promise.allSettled([
    get<BybitList<{
      lastPrice: string;
      price24hPcnt: string;
      fundingRate: string;
      nextFundingTime: string;
    }>>(`${BYBIT}/v5/market/tickers?category=linear&symbol=${symbol}`),
    get<BybitList<unknown[]>>(
      `${BYBIT}/v5/market/kline?category=linear&symbol=${symbol}&interval=60&limit=100`
    ),
    get<BybitList<unknown[]>>(
      `${BYBIT}/v5/market/kline?category=linear&symbol=${symbol}&interval=240&limit=60`
    ),
    get<BybitList<{ openInterest: string }>>(
      `${BYBIT}/v5/market/open-interest?category=linear&symbol=${symbol}&intervalTime=1h&limit=25`
    ),
    get<BybitList<{ buyRatio: string; sellRatio: string }>>(
      `${BYBIT}/v5/market/account-ratio?category=linear&symbol=${symbol}&period=1h&limit=1`
    ),
  ]);

  if (
    tickers.status !== "fulfilled" ||
    !tickers.value.result?.list?.length ||
    k1h.status !== "fulfilled" ||
    !k1h.value.result?.list?.length
  ) {
    throw new Error("bybit core data unavailable");
  }

  const t = tickers.value.result.list[0];
  // Bybit klines are newest-first: [start, open, high, low, close, vol, turnover]
  const klines1h = [...k1h.value.result.list]
    .reverse()
    .map((c) => [num(c[0]), num(c[1]), num(c[2]), num(c[3]), num(c[4])]);
  const closes4h =
    k4h.status === "fulfilled"
      ? [...k4h.value.result.list].reverse().map((c) => num(c[4]))
      : [];

  let oi: number | null = null;
  if (oiHist.status === "fulfilled" && oiHist.value.result?.list?.length >= 24) {
    const list = [...oiHist.value.result.list].reverse(); // chronological
    const then = num(list[0].openInterest);
    const now = num(list[list.length - 1].openInterest);
    if (then > 0) oi = ((now - then) / then) * 100;
  }

  let ls: number | null = null;
  if (ratio.status === "fulfilled" && ratio.value.result?.list?.length) {
    const r = ratio.value.result.list[0];
    const sell = num(r.sellRatio);
    if (sell > 0) ls = num(r.buyRatio) / sell;
  }

  return {
    source: "Bybit",
    mark: num(t.lastPrice),
    change24h: num(t.price24hPcnt) * 100,
    fundingPct8h: num(t.fundingRate) * 100,
    nextFundingMs: num(t.nextFundingTime),
    klines1h,
    closes4h,
    oiChange24hPct: oi,
    lsRatio: ls,
    takerAvg: null, // not available on Bybit public API — scored neutral
  };
}

// ── TA helpers ────────────────────────────────────────────────────────────

function ema(closes: number[], period: number): number {
  if (closes.length < period) return closes[closes.length - 1] ?? 0;
  const k = 2 / (period + 1);
  let val = closes.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (let i = period; i < closes.length; i++) {
    val = closes[i] * k + val * (1 - k);
  }
  return val;
}

function atrPercent(klines: number[][], period = 14): number {
  if (klines.length < period + 1) return 1.5;
  const trs: number[] = [];
  for (let i = 1; i < klines.length; i++) {
    const high = klines[i][2];
    const low = klines[i][3];
    const prevClose = klines[i - 1][4];
    trs.push(
      Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose))
    );
  }
  const atr = trs.slice(-period).reduce((a, b) => a + b, 0) / period;
  const price = klines[klines.length - 1][4];
  return price > 0 ? (atr / price) * 100 : 1.5;
}

// ── Ticket builder ────────────────────────────────────────────────────────

function buildTicket(display: string, symbol: string, raw: RawPerp): PerpTicket {
  const warnings: string[] = [];
  const components: PerpComponent[] = [];
  const closes1h = raw.klines1h.map((c) => c[4]);
  const mark = raw.mark;

  if (mark <= 0 || closes1h.length < 30) {
    throw new Error(`${display}: insufficient data`);
  }

  // 1. Funding (25%) — contrarian. Baseline funding is +0.01%/8h.
  const f = raw.fundingPct8h;
  let fundScore = 0;
  if (f >= 0.05) fundScore = -90;
  else if (f >= 0.03) fundScore = -60;
  else if (f >= 0.018) fundScore = -30;
  else if (f <= -0.03) fundScore = 80;
  else if (f <= -0.01) fundScore = 40;
  components.push({
    name: "Funding rate",
    weightPct: 25,
    score: fundScore,
    detail: `${f.toFixed(4)}%/8h ${
      fundScore < 0 ? "(longs crowded, paying)" : fundScore > 0 ? "(shorts paying — squeeze fuel)" : "(normal)"
    }`,
  });

  // 2. OI × price regime (25%)
  let regime = "FLAT — no clear positioning shift";
  let regimeScore = 0;
  const oi = raw.oiChange24hPct;
  if (oi === null) {
    warnings.push("OI history unavailable — regime read skipped");
    components.push({ name: "OI × price regime", weightPct: 25, score: 0, detail: "unavailable" });
  } else {
    const pUp = raw.change24h > 1;
    const pDown = raw.change24h < -1;
    const oiUp = oi > 1.5;
    const oiDown = oi < -1.5;
    if (pUp && oiUp) { regime = "TREND CONFIRMED — price ↑ with new money (OI ↑)"; regimeScore = 60; }
    else if (pUp && oiDown) { regime = "SHORT COVERING — price ↑ but OI ↓, rally may fade"; regimeScore = -20; }
    else if (pDown && oiUp) { regime = "SHORTS PRESSING — price ↓ with new shorts (OI ↑)"; regimeScore = -60; }
    else if (pDown && oiDown) { regime = "LIQUIDATION FLUSH — price ↓ and positions closing, bounce zone"; regimeScore = 25; }
    components.push({
      name: "OI × price regime",
      weightPct: 25,
      score: regimeScore,
      detail: `24h price ${raw.change24h.toFixed(1)}%, OI ${oi >= 0 ? "+" : ""}${oi.toFixed(1)}%`,
    });
  }

  // 3. Trend structure (25%)
  const ema20_1h = ema(closes1h, 20);
  const ema50_1h = ema(closes1h, 50);
  const ema20_4h = raw.closes4h.length >= 20 ? ema(raw.closes4h, 20) : mark;
  const ema50_4h = raw.closes4h.length >= 50 ? ema(raw.closes4h, 50) : ema20_4h;
  const above = [mark > ema20_1h, mark > ema50_1h, mark > ema20_4h, mark > ema50_4h].filter(Boolean).length;
  const trendScore = (above / 4) * 200 - 100;
  components.push({
    name: "Trend structure",
    weightPct: 25,
    score: trendScore,
    detail: `above ${above}/4 EMAs (1h+4h EMA20/50)`,
  });

  // 4. Taker flow (15%)
  if (raw.takerAvg === null) {
    components.push({ name: "Taker flow", weightPct: 15, score: 0, detail: "unavailable on this source" });
  } else {
    const ta = raw.takerAvg;
    let takerScore = 0;
    if (ta >= 1.15) takerScore = 70;
    else if (ta >= 1.05) takerScore = 35;
    else if (ta <= 0.87) takerScore = -70;
    else if (ta <= 0.95) takerScore = -35;
    components.push({
      name: "Taker flow",
      weightPct: 15,
      score: takerScore,
      detail: `buy/sell ${ta.toFixed(2)} (6h avg)`,
    });
  }

  // 5. Long/short accounts (10%) — contrarian at extremes
  if (raw.lsRatio === null) {
    components.push({ name: "Long/short accounts", weightPct: 10, score: 0, detail: "unavailable" });
  } else {
    const ls = raw.lsRatio;
    let lsScore = 0;
    if (ls >= 3) lsScore = -60;
    else if (ls >= 2.2) lsScore = -30;
    else if (ls <= 0.7) lsScore = 60;
    else if (ls <= 0.9) lsScore = 30;
    components.push({
      name: "Long/short accounts",
      weightPct: 10,
      score: lsScore,
      detail: `${ls.toFixed(2)} ${ls >= 2.2 ? "(crowded longs)" : ls <= 0.9 ? "(crowded shorts)" : "(balanced)"}`,
    });
  }

  const bias = Math.max(
    -100,
    Math.min(100, components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0))
  );

  const direction: PerpTicket["direction"] =
    bias >= 25 ? "LONG" : bias <= -25 ? "SHORT" : "STAND ASIDE";
  const confidence: PerpTicket["confidence"] =
    Math.abs(bias) >= 55 ? "HIGH" : Math.abs(bias) >= 35 ? "MEDIUM" : "LOW";

  const atr = atrPercent(raw.klines1h, 14);
  const stopPct = Math.min(6, Math.max(0.6, atr * 1.5));
  const isLong = direction !== "SHORT";
  const stopPrice = isLong ? mark * (1 - stopPct / 100) : mark * (1 + stopPct / 100);
  const tp1 = isLong ? mark * (1 + (stopPct * 1.5) / 100) : mark * (1 - (stopPct * 1.5) / 100);
  const tp2 = isLong ? mark * (1 + (stopPct * 3) / 100) : mark * (1 - (stopPct * 3) / 100);
  const maxLev = Math.max(1, Math.min(20, Math.floor(45 / stopPct)));

  let squeezeWatch: string | null = null;
  if (oi !== null) {
    if (f >= 0.03 && oi > 3) {
      squeezeWatch = "SQUEEZE WATCH: crowded longs paying heavy funding with OI rising — long-squeeze risk";
    } else if (f <= -0.02 && oi > 3) {
      squeezeWatch = "SQUEEZE WATCH: shorts paying funding with OI rising — short-squeeze fuel building";
    }
  }

  return {
    symbol,
    display,
    source: raw.source,
    markPrice: mark,
    change24h: raw.change24h,
    bias: Math.round(bias),
    direction,
    confidence,
    regime,
    components,
    entry: mark,
    pullbackEntry: ema20_1h,
    stopPct: Number(stopPct.toFixed(2)),
    stopPrice,
    tp1,
    tp2,
    atrPct: Number(atr.toFixed(2)),
    maxLev,
    fundingPct8h: Number(f.toFixed(4)),
    nextFundingMs: raw.nextFundingMs,
    oiChange24hPct: oi === null ? 0 : Number(oi.toFixed(1)),
    squeezeWatch,
    warnings,
    whale: null,
  };
}

// ── Whale prints: large aggressive trades on the perp book ───────────────

/** Notional threshold per symbol for a trade to count as a whale print. */
function whaleThreshold(display: string): number {
  if (display === "BTC" || display === "ETH") return 250_000;
  return 50_000;
}

async function fetchBinanceWhales(
  symbol: string,
  thresholdUsd: number
): Promise<WhalePrints | null> {
  try {
    const trades = await get<{ p: string; q: string; m: boolean; T: number }[]>(
      `${BINANCE}/fapi/v1/aggTrades?symbol=${symbol}&limit=1000`
    );
    if (!trades.length) return null;
    let buy = 0, sell = 0, largest = 0, count = 0;
    for (const t of trades) {
      const usd = num(t.p) * num(t.q);
      if (usd < thresholdUsd) continue;
      count++;
      largest = Math.max(largest, usd);
      // m=true → buyer was maker → taker SOLD aggressively
      if (t.m) sell += usd;
      else buy += usd;
    }
    const windowMin = Math.max(
      1,
      Math.round((trades[trades.length - 1].T - trades[0].T) / 60_000)
    );
    return { buyUsd: buy, sellUsd: sell, netUsd: buy - sell, largestUsd: largest, count, windowMin, thresholdUsd };
  } catch {
    return null;
  }
}

async function fetchBybitWhales(
  symbol: string,
  thresholdUsd: number
): Promise<WhalePrints | null> {
  try {
    const data = await get<BybitList<{ price: string; size: string; side: string; time: string }>>(
      `${BYBIT}/v5/market/recent-trade?category=linear&symbol=${symbol}&limit=1000`
    );
    const trades = data.result?.list ?? [];
    if (!trades.length) return null;
    let buy = 0, sell = 0, largest = 0, count = 0;
    let minT = Infinity, maxT = 0;
    for (const t of trades) {
      const usd = num(t.price) * num(t.size);
      const ts = num(t.time);
      minT = Math.min(minT, ts);
      maxT = Math.max(maxT, ts);
      if (usd < thresholdUsd) continue;
      count++;
      largest = Math.max(largest, usd);
      if (t.side === "Buy") buy += usd;
      else sell += usd;
    }
    const windowMin = Math.max(1, Math.round((maxT - minT) / 60_000));
    return { buyUsd: buy, sellUsd: sell, netUsd: buy - sell, largestUsd: largest, count, windowMin, thresholdUsd };
  } catch {
    return null;
  }
}

export async function buildPerpTicket(
  symbol: string,
  display: string
): Promise<PerpTicket> {
  const threshold = whaleThreshold(display);
  try {
    const raw = await fetchBinance(symbol);
    const ticket = buildTicket(display, symbol, raw);
    ticket.whale = await fetchBinanceWhales(symbol, threshold);
    return ticket;
  } catch {
    // Binance blocked or down — Bybit fallback
    const raw = await fetchBybit(symbol);
    const ticket = buildTicket(display, symbol, raw);
    ticket.whale = await fetchBybitWhales(symbol, threshold);
    return ticket;
  }
}

export async function buildAllTickets(): Promise<PerpTicket[]> {
  const results = await Promise.allSettled(
    PERP_SYMBOLS.map((s) => buildPerpTicket(s.symbol, s.display))
  );
  const tickets = results
    .filter((r): r is PromiseFulfilledResult<PerpTicket> => r.status === "fulfilled")
    .map((r) => r.value);
  if (!tickets.length) {
    throw new Error("Both Binance and Bybit unreachable");
  }
  return tickets.sort((a, b) => Math.abs(b.bias) - Math.abs(a.bias));
}
