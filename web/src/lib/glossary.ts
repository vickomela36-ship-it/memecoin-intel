// Shared glossary — the single source used by both the Education modal and the
// inline <Term> tooltip so a definition never drifts between the two.

export interface GlossaryEntry { term: string; def: string }

export const GLOSSARY: GlossaryEntry[] = [
  { term: "Slippage", def: "The gap between the price you expect and the price you actually get. On thin liquidity, a market buy can fill far worse than the screen shows." },
  { term: "LP (Liquidity Pool)", def: "The paired token+SOL reserve that lets people trade. If it's unlocked, the dev can withdraw it and the price goes to zero — a rug." },
  { term: "TVL", def: "Total Value Locked — the dollar amount sitting in a protocol/pool. For a memecoin, roughly the liquidity depth." },
  { term: "Bundling", def: "A dev splitting supply across many wallets at launch to hide concentration, then selling in coordination. Looks organic, isn't." },
  { term: "Honeypot", def: "A token you can buy but can't sell — usually via freeze authority. The chart looks up-only because nobody can exit." },
  { term: "CTO", def: "Community Takeover — the original dev abandoned the token and holders took over marketing/development." },
  { term: "Vamping", def: "A correctly-named or better-executed token stealing a narrative from the coin that ran first. The first mover dies when the 'real' one appears." },
  { term: "Market structure", def: "The sequence of swing highs and lows. Higher highs + higher lows = uptrend; lower highs + lower lows = downtrend." },
  { term: "Break of structure (BOS)", def: "Price breaking the most recent swing high (bullish) or low (bearish), signaling the trend may be shifting." },
  { term: "Fib retracement", def: "Fibonacci levels (0.5, 0.618, 0.786) drawn from a swing low to high, marking zones where a pullback often finds support." },
  { term: "Bonding curve", def: "The pricing mechanism on launchpads like pump.fun — price rises as more is bought, until the token 'graduates' to a real DEX pool." },
  { term: "Graduation", def: "When a launchpad token fills its bonding curve and migrates to a full DEX (e.g. Raydium) with a standard liquidity pool." },
  { term: "Fresh wallet", def: "A wallet created recently with no prior history. Several in the top holders of a new launch = a coordinated, likely-insider launch." },
  { term: "Market maker", def: "An entity (often a bot) providing continuous buy/sell orders. On memecoins it can manufacture a fake, too-regular chart." },
];

// Keyed lookup for the inline tooltip. Keys are lowercase short aliases.
const BY_KEY: Record<string, GlossaryEntry> = {};
for (const e of GLOSSARY) {
  BY_KEY[e.term.toLowerCase()] = e;
  const short = e.term.split(" (")[0].toLowerCase();
  BY_KEY[short] = e;
}
BY_KEY["lp"] = BY_KEY["lp (liquidity pool)"];
BY_KEY["bos"] = BY_KEY["break of structure (bos)"];
BY_KEY["fib"] = BY_KEY["fib retracement"];

export function lookupTerm(key: string): GlossaryEntry | null {
  return BY_KEY[key.toLowerCase()] ?? null;
}
