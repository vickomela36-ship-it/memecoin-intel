import { NextRequest, NextResponse } from "next/server";
import { unstable_cache } from "next/cache";
import type { WhaleTokenIntel } from "@/types";

export const dynamic = "force-dynamic";

// Keys already live in this repo's Python config; env vars override.
const HELIUS_KEY =
  process.env.HELIUS_API_KEY ?? "8292769f-aeb2-471c-af1d-fb98576972e4";
const BIRDEYE_KEY =
  process.env.BIRDEYE_API_KEY ?? "dac9521a4c004f65897b2bd3e52cf10d";

const WHALE_TRADE_MIN_USD = 300;

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

async function heliusRpc<T>(method: string, params: unknown[]): Promise<T | null> {
  try {
    const res = await fetch(
      `https://mainnet.helius-rpc.com/?api-key=${HELIUS_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
        cache: "no-store",
      }
    );
    if (!res.ok) return null;
    const data = await res.json();
    return (data?.result as T) ?? null;
  } catch {
    return null;
  }
}

interface LargestAccounts {
  value: { address: string; uiAmount: number | null }[];
}
interface TokenSupply {
  value: { uiAmount: number | null };
}

async function holderConcentration(mint: string) {
  const [largest, supply] = await Promise.all([
    heliusRpc<LargestAccounts>("getTokenLargestAccounts", [mint]),
    heliusRpc<TokenSupply>("getTokenSupply", [mint]),
  ]);
  const total = num(supply?.value?.uiAmount);
  const accounts = (largest?.value ?? [])
    .map((a) => num(a.uiAmount))
    .filter((v) => v > 0)
    .sort((a, b) => b - a);
  if (total <= 0 || !accounts.length) {
    return { top1: null, top5: null, top10: null, sampled: 0 };
  }
  const pct = (n: number) =>
    Number(
      ((accounts.slice(0, n).reduce((a, b) => a + b, 0) / total) * 100).toFixed(1)
    );
  return {
    top1: pct(1),
    top5: pct(5),
    top10: pct(10),
    sampled: accounts.length,
  };
}

interface BirdeyeTx {
  side?: string;
  txType?: string;
  volume_usd?: number;
  volumeUSD?: number;
  volumeUsd?: number;
}

async function whaleTrades(mint: string) {
  try {
    const res = await fetch(
      `https://public-api.birdeye.so/defi/txs/token?address=${mint}&offset=0&limit=50&tx_type=swap&sort_type=desc`,
      {
        headers: { "X-API-KEY": BIRDEYE_KEY, "x-chain": "solana" },
        cache: "no-store",
      }
    );
    if (!res.ok) return null;
    const data = await res.json();
    const items: BirdeyeTx[] = data?.data?.items ?? [];
    if (!items.length) return null;

    let buy = 0,
      sell = 0,
      largest = 0,
      counted = 0;
    for (const t of items) {
      const usd = num(t.volume_usd ?? t.volumeUSD ?? t.volumeUsd);
      if (usd < WHALE_TRADE_MIN_USD) continue;
      counted++;
      largest = Math.max(largest, usd);
      const side = String(t.side ?? t.txType ?? "").toLowerCase();
      if (side.includes("buy")) buy += usd;
      else if (side.includes("sell")) sell += usd;
    }
    return { buy, sell, largest, sampled: counted };
  } catch {
    return null;
  }
}

function readFlags(
  conc: { top1: number | null; top10: number | null },
  trades: { buy: number; sell: number } | null
): string[] {
  const flags: string[] = [];
  if (conc.top10 !== null) {
    if (conc.top10 >= 70) flags.push("INSIDER-HEAVY: top10 hold " + conc.top10 + "%");
    else if (conc.top10 >= 50) flags.push("Concentrated (top10 " + conc.top10 + "%)");
    else flags.push("Distribution OK");
  }
  if (trades) {
    const net = trades.buy - trades.sell;
    if (net > 2000) flags.push("Whales ACCUMULATING");
    else if (net < -2000) flags.push("Whales DISTRIBUTING");
    else if (trades.buy + trades.sell > 0) flags.push("Whale flow balanced");
  }
  return flags;
}

const getWhaleIntel = unstable_cache(
  async (tokensParam: string): Promise<WhaleTokenIntel[]> => {
    const tokens = tokensParam
      .split(",")
      .map((t) => {
        const [address, symbol] = t.split("|");
        return { address, symbol: symbol ?? "?" };
      })
      .filter((t) => /^[A-Za-z0-9]{30,50}$/.test(t.address))
      .slice(0, 8);

    return Promise.all(
      tokens.map(async (t, i) => {
        // Concentration for all; trade flow only for the first 4 (rate limits)
        const [conc, trades] = await Promise.all([
          holderConcentration(t.address),
          i < 4 ? whaleTrades(t.address) : Promise.resolve(null),
        ]);
        return {
          address: t.address,
          symbol: t.symbol,
          top1Pct: conc.top1,
          top5Pct: conc.top5,
          top10Pct: conc.top10,
          holdersSampled: conc.sampled,
          whaleBuyUsd: trades ? Math.round(trades.buy) : null,
          whaleSellUsd: trades ? Math.round(trades.sell) : null,
          netUsd: trades ? Math.round(trades.buy - trades.sell) : null,
          largestTradeUsd: trades ? Math.round(trades.largest) : null,
          tradesSampled: trades?.sampled ?? 0,
          flags: readFlags(conc, trades),
        };
      })
    );
  },
  ["whale-intel"],
  { revalidate: 300 }
);

export async function GET(req: NextRequest) {
  const tokensParam = new URL(req.url).searchParams.get("tokens");
  if (!tokensParam) {
    return NextResponse.json({ error: "tokens param required" }, { status: 400 });
  }
  try {
    return NextResponse.json(await getWhaleIntel(tokensParam));
  } catch {
    return NextResponse.json({ error: "whale intel failed" }, { status: 502 });
  }
}
