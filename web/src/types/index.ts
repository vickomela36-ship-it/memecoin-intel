// ── Shared ────────────────────────────────────────────────────────────────

export type ModuleId = "memecoin" | "football" | "crypto";

export type TabId = ModuleId | "challenge" | "portfolio";

export interface ScoreComponent {
  name: string;
  weightPct: number;
  score: number; // 0-100 contribution before weighting
  detail: string;
}

// ── Accuracy tracking ─────────────────────────────────────────────────────

export interface SignalLog {
  id: string;
  module: ModuleId;
  timestamp: number;
  signal: {
    type: string; // 'launch' | 'recovery' | 'edge' | 'score'
    target: string; // token address/symbol or match id
    direction: string; // 'bullish' | 'bearish' | 'home' | 'away' | 'draw'
    score: number;
    details: Record<string, unknown>;
  };
  outcome: {
    resolved: boolean;
    result: "hit" | "miss" | "partial" | "voided" | null;
    priceAtSignal: number;
    priceAtResolution: number | null;
    resolvedAt: number | null;
  };
}

export interface ModuleAccuracy {
  module: ModuleId;
  fired: number;
  resolved: number;
  hits: number;
  hitRate: number | null; // null until >= 5 resolved
  note: string;
}

// ── Memecoin ──────────────────────────────────────────────────────────────

export interface DexPair {
  chainId: string;
  pairAddress: string;
  url?: string;
  baseToken?: { address: string; symbol: string; name: string };
  priceUsd?: string;
  priceChange?: { m5?: number; h1?: number; h6?: number; h24?: number };
  volume?: { m5?: number; h1?: number; h6?: number; h24?: number };
  liquidity?: { usd?: number };
  fdv?: number;
  txns?: Record<string, { buys?: number; sells?: number }>;
  pairCreatedAt?: number;
}

export interface MemeSignal {
  mode: "LAUNCH" | "RECOVERY" | "HIGHER-CAP" | "DEGEN" | "SURE" | "MOMENTUM";
  /** Human category, e.g. "2x GRINDER", "3x RECOVERY", "MOMENTUM RIDER" */
  playType: string;
  address: string;
  symbol: string;
  name: string;
  priceUsd: number;
  score: number;
  components: ScoreComponent[];
  reasons: string[];
  warnings: string[];
  fdv: number;
  liquidity: number;
  volH1: number;
  vol24h: number;
  ageHours: number;
  buySellRatio: number;
  pairUrl: string;
  boosts: number;
  /** Price-change intel */
  m5: number;
  h1: number;
  h6: number;
  h24: number;
  /** Total txns (buys+sells) in the last hour */
  txns1h: number;
  /** Sizing rule key for the trade plan: A / B / 3x POSSIBLE / 5x POTENTIAL / 10x RUNNER / 100x MOONSHOT */
  sizingKey: string;
  /** Degen multiplier tier, e.g. "10x RUNNER" (DEGEN mode only) */
  tier?: string;
  riskLevel?: string;
}

export interface ScanPulse {
  discovered: number;
  analyzed: number;
  greenPct: number; // % of analyzed tokens green on 24h
  medianH24: number;
  totalVol24hUsd: number;
}

export interface MemeScanResult {
  pulse: ScanPulse;
  sure2x: MemeSignal[];
  recovery3x: MemeSignal[];
  momentum: MemeSignal[];
  higherCap: MemeSignal[];
  launches: MemeSignal[];
  degens: MemeSignal[];
}

// ── Football ──────────────────────────────────────────────────────────────

export interface FootballMatch {
  id: number;
  utcDate: string;
  status: string;
  homeTeam: { name: string };
  awayTeam: { name: string };
  competition?: { name: string; code?: string };
  score?: { fullTime?: { home: number | null; away: number | null } };
}

export interface OddsEvent {
  id: string;
  home_team: string;
  away_team: string;
  commence_time: string;
  bookmakers: {
    title: string;
    markets: { key: string; outcomes: { name: string; price: number }[] }[];
  }[];
}

export interface BinaryQuestion {
  key: "home" | "draw" | "away";
  question: string; // "ARSENAL TO WIN?"
  fairProb: number; // 0-1, de-vigged consensus blended with ELO
  buyYesBelow: number; // cents — YES has value below this price
  buyNoAbove: number; // cents — NO has value above this price
  kellyYesPct: number; // Kelly % of bankroll if YES bought at threshold
  tier: "STRONG" | "LEAN" | "PASS";
}

export interface MatchEdge {
  matchId: number;
  home: string;
  away: string;
  competition: string;
  kickoff: string;
  homeElo: number;
  awayElo: number;
  modelProbs: { home: number; draw: number; away: number };
  consensusProbs: { home: number; draw: number; away: number } | null;
  booksCount: number;
  questions: BinaryQuestion[];
  hasStrong: boolean;
}

// ── Whale / insider intel ─────────────────────────────────────────────────

export interface WhaleTokenIntel {
  address: string;
  symbol: string;
  top1Pct: number | null;
  top5Pct: number | null;
  top10Pct: number | null;
  holdersSampled: number;
  whaleBuyUsd: number | null;
  whaleSellUsd: number | null;
  netUsd: number | null;
  largestTradeUsd: number | null;
  tradesSampled: number;
  flags: string[];
}

/** Large aggressive trades on the perp book. */
export interface WhalePrints {
  buyUsd: number;
  sellUsd: number;
  netUsd: number;
  largestUsd: number;
  count: number;
  windowMin: number;
  thresholdUsd: number;
}

// ── Perp Desk ─────────────────────────────────────────────────────────────

/** Component score is -100 (max short) .. +100 (max long). */
export interface PerpComponent {
  name: string;
  weightPct: number;
  score: number;
  detail: string;
}

export interface PerpTicket {
  symbol: string; // BTCUSDT
  display: string; // BTC
  source: "Binance" | "Bybit";
  markPrice: number;
  change24h: number;
  bias: number; // -100..+100
  direction: "LONG" | "SHORT" | "STAND ASIDE";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  regime: string;
  components: PerpComponent[];
  entry: number;
  pullbackEntry: number; // 1h EMA20
  stopPct: number;
  stopPrice: number;
  tp1: number;
  tp2: number;
  atrPct: number;
  maxLev: number;
  fundingPct8h: number;
  nextFundingMs: number;
  oiChange24hPct: number;
  squeezeWatch: string | null;
  warnings: string[];
  whale: WhalePrints | null;
}

// ── Crypto ────────────────────────────────────────────────────────────────

export interface GeckoCoin {
  id: string;
  symbol: string;
  name: string;
  current_price: number;
  market_cap: number;
  total_volume: number;
  price_change_percentage_1h_in_currency?: number;
  price_change_percentage_24h_in_currency?: number;
  price_change_percentage_7d_in_currency?: number;
  sparkline_in_7d?: { price: number[] };
}

export interface CryptoScoreRow {
  id: string;
  symbol: string;
  name: string;
  price: number;
  score: number;
  direction: "bullish" | "bearish" | "neutral";
  label: string;
  components: ScoreComponent[];
  sparkline: number[];
  change24h: number;
}
