import type { DexPair } from "@/types";
import { jsonFetcher } from "@/lib/utils";

const DS = "https://api.dexscreener.com";

interface BoostEntry {
  tokenAddress: string;
  chainId?: string;
  totalAmount?: number;
  amount?: number;
}

/** Search queries that surface active Solana meme pairs beyond the boost feeds. */
const SEARCH_QUERIES = [
  "SOL", "PUMP", "MEME", "BONK", "WIF", "PEPE",
  "DOGE", "CAT", "AI", "TRUMP", "MOON", "SOLANA",
];

/**
 * Discover candidate Solana token addresses from DexScreener boost feeds,
 * profile feed, AND search queries — several hundred candidates per scan.
 */
export async function discoverTokens(): Promise<
  { address: string; boosts: number }[]
> {
  const feedEndpoints = [
    `${DS}/token-boosts/top/v1`,
    `${DS}/token-boosts/latest/v1`,
    `${DS}/token-profiles/latest/v1`,
  ];

  const [feedResults, searchResults] = await Promise.all([
    Promise.allSettled(feedEndpoints.map((u) => jsonFetcher<BoostEntry[]>(u))),
    Promise.allSettled(
      SEARCH_QUERIES.map((q) =>
        jsonFetcher<{ pairs: DexPair[] | null }>(
          `${DS}/latest/dex/search?q=${encodeURIComponent(q)}`
        )
      )
    ),
  ]);

  const seen = new Set<string>();
  const out: { address: string; boosts: number }[] = [];

  for (const r of feedResults) {
    if (r.status !== "fulfilled" || !Array.isArray(r.value)) continue;
    for (const t of r.value) {
      const addr = t.tokenAddress;
      const chain = t.chainId;
      if (!addr || seen.has(addr)) continue;
      if (chain && chain !== "solana") continue;
      seen.add(addr);
      out.push({ address: addr, boosts: t.totalAmount ?? t.amount ?? 0 });
    }
  }

  for (const r of searchResults) {
    if (r.status !== "fulfilled") continue;
    for (const p of r.value?.pairs ?? []) {
      if (p.chainId !== "solana") continue;
      const addr = p.baseToken?.address;
      if (!addr || seen.has(addr)) continue;
      seen.add(addr);
      out.push({ address: addr, boosts: 0 });
    }
  }

  return out.slice(0, 270); // 9 batches of 30 — wide but rate-friendly
}

/** Batch-fetch pair data — DexScreener accepts up to 30 comma-joined addresses. */
export async function fetchPairsBatch(
  addresses: string[]
): Promise<Map<string, DexPair[]>> {
  const map = new Map<string, DexPair[]>();
  const chunks: string[][] = [];
  for (let i = 0; i < addresses.length; i += 30) {
    chunks.push(addresses.slice(i, i + 30));
  }

  const results = await Promise.allSettled(
    chunks.map((chunk) =>
      jsonFetcher<{ pairs: DexPair[] | null }>(
        `${DS}/latest/dex/tokens/${chunk.join(",")}`
      )
    )
  );

  for (const r of results) {
    if (r.status !== "fulfilled") continue;
    const pairs = r.value?.pairs ?? [];
    for (const p of pairs) {
      const base = p.baseToken?.address;
      if (!base) continue;
      const list = map.get(base) ?? [];
      list.push(p);
      map.set(base, list);
    }
  }
  return map;
}

/** Single-token refetch (used by the accuracy resolver). */
export async function fetchTokenPrice(address: string): Promise<number | null> {
  try {
    const data = await jsonFetcher<{ pairs: DexPair[] | null }>(
      `${DS}/latest/dex/tokens/${address}`
    );
    const pairs = (data.pairs ?? []).filter((p) => p.chainId === "solana");
    if (!pairs.length) return null;
    const best = pairs.reduce((a, b) =>
      (Number(a.volume?.h24) || 0) >= (Number(b.volume?.h24) || 0) ? a : b
    );
    const price = Number(best.priceUsd);
    return isFinite(price) && price > 0 ? price : null;
  } catch {
    return null;
  }
}

/** Pick the highest-24h-volume Solana pair for a token. */
export function bestSolanaPair(pairs: DexPair[]): DexPair | null {
  const sol = pairs.filter((p) => p.chainId === "solana");
  if (!sol.length) return null;
  return sol.reduce((a, b) =>
    (Number(a.volume?.h24) || 0) >= (Number(b.volume?.h24) || 0) ? a : b
  );
}
