// ── Shared ────────────────────────────────────────────────────────────────

export type ModuleId = "memecoin" | "football" | "crypto";

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
  mode: "LAUNCH" | "RECOVERY";
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

export interface OutcomeEdge {
  outcome: "home" | "draw" | "away";
  modelProb: number;
  impliedProb: number;
  edge: number;
  bestOdds: number;
  bestBook: string;
  kellyFraction: number;
  signal: "STRONG" | "MODERATE" | "NONE";
}

export interface MatchEdge {
  matchId: number;
  home: string;
  away: string;
  competition: string;
  kickoff: string;
  homeElo: number;
  awayElo: number;
  probs: { home: number; draw: number; away: number };
  edges: OutcomeEdge[];
  bestEdge: OutcomeEdge | null;
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
