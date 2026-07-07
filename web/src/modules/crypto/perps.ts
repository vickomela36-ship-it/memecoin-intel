// Perp Desk engine — positioning data from Binance's public futures API.
// Called CLIENT-SIDE on purpose: Binance geo-blocks US datacenter IPs
// (where Vercel functions run) but allows browser CORS worldwide.

import type { PerpComponent, PerpTicket } from "@/types";

const FAPI = "https://fapi.binance.com";

export const PERP_SYMBOLS: { symbol: string; display: string }[] = [
  { symbol: "BTCUSDT", display: "BTC" },
  { symbol: "ETHUSDT", display: "ETH" },
  { symbol: "SOLUSDT", display: "SOL" },
  { symbol: "DOGEUSDT", display: "DOGE" },
  { symbol: "1000PEPEUSDT", display: "PEPE" },
  { symbol: "WIFUSDT", display: "WIF" },
];

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${FAPI}${path}`);
  if (!res.ok) throw new Error(`Binance ${res.status} on ${path}`);
  return res.json();
}

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
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
    const high = num(klines[i][2]);
    const low = num(klines[i][3]);
    const prevClose = num(klines[i - 1][4]);
    trs.push(
      Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose))
    );
  }
  const atr = trs.slice(-period).reduce((a, b) => a + b, 0) / period;
  const price = num(klines[klines.length - 1][4]);
  return price > 0 ? (atr / price) * 100 : 1.5;
}

// ── Ticket builder ────────────────────────────────────────────────────────

export async function buildPerpTicket(
  symbol: string,
  display: string
): Promise<PerpTicket> {
  const [premium, ticker, k1h, k4h, oiHist, lsRatio, taker] =
    await Promise.allSettled([
      get<{ markPrice: string; lastFundingRate: string; nextFundingTime: number }>(
        `/fapi/v1/premiumIndex?symbol=${symbol}`
      ),
      get<{ priceChangePercent: string }>(`/fapi/v1/ticker/24hr?symbol=${symbol}`),
      get<number[][]>(`/fapi/v1/klines?symbol=${symbol}&interval=1h&limit=100`),
      get<number[][]>(`/fapi/v1/klines?symbol=${symbol}&interval=4h&limit=60`),
      get<{ sumOpenInterestValue: string; timestamp: number }[]>(
        `/futures/data/openInterestHist?symbol=${symbol}&period=1h&limit=25`
      ),
      get<{ longShortRatio: string }[]>(
        `/futures/data/globalLongShortAccountRatio?symbol=${symbol}&period=1h&limit=1`
      ),
      get<{ buySellRatio: string }[]>(
        `/futures/data/takerlongshortRatio?symbol=${symbol}&period=1h&limit=6`
      ),
    ]);

  const warnings: string[] = [];
  const components: PerpComponent[] = [];

  const mark =
    premium.status === "fulfilled" ? num(premium.value.markPrice) : 0;
  const fundingPct8h =
    premium.status === "fulfilled"
      ? num(premium.value.lastFundingRate) * 100
      : 0;
  const nextFundingMs =
    premium.status === "fulfilled" ? num(premium.value.nextFundingTime) : 0;
  const change24h =
    ticker.status === "fulfilled" ? num(ticker.value.priceChangePercent) : 0;
  const closes1h =
    k1h.status === "fulfilled" ? k1h.value.map((c) => num(c[4])) : [];
  const closes4h =
    k4h.status === "fulfilled" ? k4h.value.map((c) => num(c[4])) : [];

  if (mark <= 0 || closes1h.length < 30) {
    throw new Error(`${display}: insufficient Binance data`);
  }

  // 1. Funding (25%) — contrarian. Baseline funding is +0.01%/8h.
  let fundScore = 0;
  if (fundingPct8h >= 0.05) fundScore = -90;
  else if (fundingPct8h >= 0.03) fundScore = -60;
  else if (fundingPct8h >= 0.018) fundScore = -30;
  else if (fundingPct8h <= -0.03) fundScore = 80;
  else if (fundingPct8h <= -0.01) fundScore = 40;
  components.push({
    name: "Funding rate",
    weightPct: 25,
    score: fundScore,
    detail: `${fundingPct8h.toFixed(4)}%/8h ${
      fundScore < 0 ? "(longs crowded, paying)" : fundScore > 0 ? "(shorts paying — squeeze fuel)" : "(normal)"
    }`,
  });

  // 2. OI + price regime (25%)
  let oiChange24hPct = 0;
  if (oiHist.status === "fulfilled" && oiHist.value.length >= 24) {
    const now = num(oiHist.value[oiHist.value.length - 1].sumOpenInterestValue);
    const then = num(oiHist.value[0].sumOpenInterestValue);
    if (then > 0) oiChange24hPct = ((now - then) / then) * 100;
  }
  let regime = "FLAT — no clear positioning shift";
  let regimeScore = 0;
  const pUp = change24h > 1;
  const pDown = change24h < -1;
  const oiUp = oiChange24hPct > 1.5;
  const oiDown = oiChange24hPct < -1.5;
  if (pUp && oiUp) { regime = "TREND CONFIRMED — price ↑ with new money (OI ↑)"; regimeScore = 60; }
  else if (pUp && oiDown) { regime = "SHORT COVERING — price ↑ but OI ↓, rally may fade"; regimeScore = -20; }
  else if (pDown && oiUp) { regime = "SHORTS PRESSING — price ↓ with new shorts (OI ↑)"; regimeScore = -60; }
  else if (pDown && oiDown) { regime = "LIQUIDATION FLUSH — price ↓ and positions closing, bounce zone"; regimeScore = 25; }
  components.push({
    name: "OI × price regime",
    weightPct: 25,
    score: regimeScore,
    detail: `24h price ${change24h.toFixed(1)}%, OI ${oiChange24hPct >= 0 ? "+" : ""}${oiChange24hPct.toFixed(1)}%`,
  });

  // 3. Trend structure (25%) — 1h & 4h price vs EMA20/EMA50
  const ema20_1h = ema(closes1h, 20);
  const ema50_1h = ema(closes1h, 50);
  const ema20_4h = closes4h.length >= 20 ? ema(closes4h, 20) : mark;
  const ema50_4h = closes4h.length >= 50 ? ema(closes4h, 50) : ema20_4h;
  const above = [
    mark > ema20_1h,
    mark > ema50_1h,
    mark > ema20_4h,
    mark > ema50_4h,
  ].filter(Boolean).length;
  const trendScore = (above / 4) * 200 - 100;
  components.push({
    name: "Trend structure",
    weightPct: 25,
    score: trendScore,
    detail: `above ${above}/4 EMAs (1h+4h EMA20/50)`,
  });

  // 4. Taker flow (15%) — who is hitting the ask/bid, last 6h
  let takerScore = 0;
  let takerAvg = 1;
  if (taker.status === "fulfilled" && taker.value.length) {
    takerAvg =
      taker.value.reduce((a, t) => a + num(t.buySellRatio), 0) /
      taker.value.length;
    if (takerAvg >= 1.15) takerScore = 70;
    else if (takerAvg >= 1.05) takerScore = 35;
    else if (takerAvg <= 0.87) takerScore = -70;
    else if (takerAvg <= 0.95) takerScore = -35;
  }
  components.push({
    name: "Taker flow",
    weightPct: 15,
    score: takerScore,
    detail: `buy/sell ${takerAvg.toFixed(2)} (6h avg)`,
  });

  // 5. Long/short account ratio (10%) — contrarian at extremes
  let lsScore = 0;
  let ls = 1;
  if (lsRatio.status === "fulfilled" && lsRatio.value.length) {
    ls = num(lsRatio.value[0].longShortRatio);
    if (ls >= 3) lsScore = -60;
    else if (ls >= 2.2) lsScore = -30;
    else if (ls <= 0.7) lsScore = 60;
    else if (ls <= 0.9) lsScore = 30;
  }
  components.push({
    name: "Long/short accounts",
    weightPct: 10,
    score: lsScore,
    detail: `${ls.toFixed(2)} ${ls >= 2.2 ? "(crowded longs)" : ls <= 0.9 ? "(crowded shorts)" : "(balanced)"}`,
  });

  // ── Composite bias ────────────────────────────────────────────────────
  const bias = Math.max(
    -100,
    Math.min(
      100,
      components.reduce((a, c) => a + c.score * (c.weightPct / 100), 0)
    )
  );

  const direction: PerpTicket["direction"] =
    bias >= 25 ? "LONG" : bias <= -25 ? "SHORT" : "STAND ASIDE";
  const confidence: PerpTicket["confidence"] =
    Math.abs(bias) >= 55 ? "HIGH" : Math.abs(bias) >= 35 ? "MEDIUM" : "LOW";

  // ── Trade levels ──────────────────────────────────────────────────────
  const atr = atrPercent(k1h.status === "fulfilled" ? k1h.value : [], 14);
  const stopPct = Math.min(6, Math.max(0.6, atr * 1.5));
  const isLong = direction !== "SHORT"; // STAND ASIDE renders long-side levels
  const stopPrice = isLong ? mark * (1 - stopPct / 100) : mark * (1 + stopPct / 100);
  const tp1 = isLong ? mark * (1 + (stopPct * 1.5) / 100) : mark * (1 - (stopPct * 1.5) / 100);
  const tp2 = isLong ? mark * (1 + (stopPct * 3) / 100) : mark * (1 - (stopPct * 3) / 100);

  // Max leverage such that liquidation (~90/lev % away) stays ≥ 2x beyond stop
  const maxLev = Math.max(1, Math.min(20, Math.floor(45 / stopPct)));

  // Squeeze watch
  let squeezeWatch: string | null = null;
  if (fundingPct8h >= 0.03 && oiChange24hPct > 3) {
    squeezeWatch = "SQUEEZE WATCH: crowded longs paying heavy funding with OI rising — long-squeeze risk";
  } else if (fundingPct8h <= -0.02 && oiChange24hPct > 3) {
    squeezeWatch = "SQUEEZE WATCH: shorts paying funding with OI rising — short-squeeze fuel building";
  }

  if (oiHist.status !== "fulfilled") warnings.push("OI data unavailable — regime read is partial");
  if (taker.status !== "fulfilled") warnings.push("Taker flow unavailable");

  return {
    symbol,
    display,
    markPrice: mark,
    change24h,
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
    fundingPct8h: Number(fundingPct8h.toFixed(4)),
    nextFundingMs,
    oiChange24hPct: Number(oiChange24hPct.toFixed(1)),
    squeezeWatch,
    warnings,
  };
}

export async function buildAllTickets(): Promise<PerpTicket[]> {
  const results = await Promise.allSettled(
    PERP_SYMBOLS.map((s) => buildPerpTicket(s.symbol, s.display))
  );
  const tickets = results
    .filter((r): r is PromiseFulfilledResult<PerpTicket> => r.status === "fulfilled")
    .map((r) => r.value);
  if (!tickets.length) throw new Error("Binance futures API unreachable");
  // Strongest conviction first
  return tickets.sort((a, b) => Math.abs(b.bias) - Math.abs(a.bias));
}
