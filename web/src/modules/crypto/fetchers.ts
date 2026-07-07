import type { GeckoCoin } from "@/types";
import { jsonFetcher } from "@/lib/utils";

const CG = "https://api.coingecko.com/api/v3";

/** Top 20 by market cap, with 7d sparkline and 1h/24h/7d change. */
export async function fetchTopCoins(): Promise<GeckoCoin[]> {
  return jsonFetcher<GeckoCoin[]>(
    `${CG}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=20&page=1` +
      `&sparkline=true&price_change_percentage=1h,24h,7d`
  );
}

/** Top 10 meme-category coins by market cap. */
export async function fetchMemeCoins(): Promise<GeckoCoin[]> {
  return jsonFetcher<GeckoCoin[]>(
    `${CG}/coins/markets?vs_currency=usd&category=meme-token&order=market_cap_desc` +
      `&per_page=10&page=1&sparkline=true&price_change_percentage=1h,24h,7d`
  );
}

/** Merge top + meme lists, dedupe by id. */
export async function fetchCryptoUniverse(): Promise<GeckoCoin[]> {
  const results = await Promise.allSettled([fetchTopCoins(), fetchMemeCoins()]);
  const coins: GeckoCoin[] = [];
  const seen = new Set<string>();
  for (const r of results) {
    if (r.status !== "fulfilled" || !Array.isArray(r.value)) continue;
    for (const c of r.value) {
      if (!seen.has(c.id)) {
        seen.add(c.id);
        coins.push(c);
      }
    }
  }
  if (coins.length === 0) throw new Error("CoinGecko returned no data");
  return coins;
}
