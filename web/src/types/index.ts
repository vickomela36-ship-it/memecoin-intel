// ── Shared ────────────────────────────────────────────────────────────────

export type ModuleId = "memecoin";

export type TabId =
  | ModuleId
  | "confluence"
  | "intel"
  | "creators"
  | "calls"
  | "positions"
  | "challenge"
  | "portfolio";

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
  dexId?: string;
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
  mode:
    | "LAUNCH"
    | "RECOVERY"
    | "HIGHER-CAP"
    | "DEGEN"
    | "SURE"
    | "MOMENTUM"
    | "PUMPFUN"
    | "VOLUME"
    | "TRENDING"
    | "HOT";
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

export interface NarrativeIntel {
  name: string;
  tokens: number;
  greenPct: number;
  medianH24: number;
  totalVolUsd: number;
  topSymbols: string[];
}

export interface MemeScanResult {
  pulse: ScanPulse;
  metas: NarrativeIntel[];
  trending: MemeSignal[];
  hot: MemeSignal[];
  sure2x: MemeSignal[];
  recovery3x: MemeSignal[];
  momentum: MemeSignal[];
  volumePlays: MemeSignal[];
  higherCap: MemeSignal[];
  pumpfun: MemeSignal[];
  launches: MemeSignal[];
  degens: MemeSignal[];
}

// ── Safety Card ───────────────────────────────────────────────────────────

export type SafetyVerdict = "pass" | "warn" | "fail" | "unknown";

export interface SafetyCheck {
  id: string;
  label: string;
  verdict: SafetyVerdict;
  value: string; // the underlying number, shown verbatim
  explain: string; // one-line plain-English "why this matters"
}

export interface FundingCluster {
  origin: string; // funding wallet (truncated)
  holders: number; // how many top holders it funded
  withinHours: number | null;
  pctOfSupply: number | null;
}

export interface HolderRow {
  owner: string;
  pct: number;
  insider: boolean;
  isLp: boolean;
}

export interface CoinTypeInfo {
  type: string;
  confidence: string;
  reason: string;
  horizon: string;
}

export interface BottedFlag {
  pattern: string;
  confidence: number;
  explain: string;
  range: [number, number] | null; // offending candle index range, if localized
}

export interface NarrativeCompetitorLite {
  symbol: string;
  address: string;
  ageHours: number;
  fdv: number;
  vol24: number;
  isLeaderByVol: boolean;
  canonicalMatch: boolean;
  identity: number;
  moat: number;
  gravity: number;
  leaderScore: number;
  leaderNote: string;
}

export interface CollisionInfo {
  keyword: string;
  competitors: NarrativeCompetitorLite[];
  vampRisk: boolean;
  vampReason: string;
}

// ── Chart / market-structure TA (serialized view of lib/ta.ts) ─────────────

export interface ChartLevel {
  ratio: number;
  price: number;
  golden: boolean;
}

export interface ChartConfluenceSignal {
  kind: string;
  price: number;
  detail: string;
}

export interface ChartInfo {
  usable: boolean;
  suppressReason: string | null;
  anchorMode: "body" | "wick";
  price: number;
  structure: {
    state: "UPTREND" | "DOWNTREND" | "RANGING" | "REVERSAL FORMING";
    detail: string;
  };
  fib: {
    drawn: boolean;
    reason: string;
    low: number;
    high: number;
    levels: ChartLevel[];
    goldenPocket: [number, number] | null;
    inGoldenPocket: boolean;
  } | null;
  confluence: {
    signals: ChartConfluenceSignal[];
    count: number;
    grade: string;
  } | null;
  invalidation: {
    level: number | null;
    basis: string;
    confirmed: boolean;
    note: string;
  } | null;
}

export interface SafetyReport {
  mint: string;
  symbol: string;
  name: string;
  fetchedAt: number;
  verdict: SafetyVerdict; // overall
  checks: SafetyCheck[];
  coinType: CoinTypeInfo | null;
  botted: BottedFlag[];
  collision: CollisionInfo | null;
  chart: ChartInfo | null;
  holders: HolderRow[];
  holderCount: number | null;
  creator: {
    address: string | null;
    status: "accumulating" | "holding" | "distributing" | "unknown";
    note: string;
    balancePct: number | null; // creator's current holding as % of supply, if measured
  };
  deep: {
    ran: boolean;
    freshWallets: number | null;
    topSampled: number;
    fundingClusters: FundingCluster[];
    note: string;
    clusterTrend: string | null; // measured change in cluster supply since last scan
  } | null;
  sources: string[]; // which providers answered
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
