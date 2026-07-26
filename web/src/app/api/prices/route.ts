import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Shared price fetch — Portfolio, Positions, and the watch popup all need
// live prices for the same address sets. This one route (edge-cached 25s)
// coalesces them: DexScreener is hit once per 25s regardless of how many
// components or devices are asking. Batched 30 addresses per DexScreener call.

interface DexPair {
  chainId?: string;
  baseToken?: { address?: string };
  priceUsd?: string;
  priceChange?: { h1?: number; h24?: number };
  volume?: { h24?: number };
}

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

export async function GET(req: NextRequest) {
  const raw = new URL(req.url).searchParams.get("addrs") ?? "";
  const addrs = raw
    .split(",")
    .map((a) => a.trim())
    .filter((a) => /^[A-Za-z0-9]{30,50}$/.test(a))
    .slice(0, 60);
  if (!addrs.length) return NextResponse.json({ prices: {} });

  const out: Record<string, { price: number; h24: number; h1: number }> = {};
  const chunks: string[][] = [];
  for (let i = 0; i < addrs.length; i += 30) chunks.push(addrs.slice(i, i + 30));

  const results = await Promise.allSettled(
    chunks.map((c) =>
      fetch(`https://api.dexscreener.com/latest/dex/tokens/${c.join(",")}`, {
        // Edge-cache identical batches for 25s
        next: { revalidate: 25 },
      }).then((r) => (r.ok ? r.json() : { pairs: [] }))
    )
  );

  const best = new Map<string, DexPair>();
  for (const r of results) {
    if (r.status !== "fulfilled") continue;
    for (const p of (r.value?.pairs ?? []) as DexPair[]) {
      if (p.chainId !== "solana") continue;
      const a = p.baseToken?.address;
      if (!a) continue;
      const prev = best.get(a);
      if (!prev || num(p.volume?.h24) > num(prev.volume?.h24)) best.set(a, p);
    }
  }
  best.forEach((p, a) => {
    const price = num(p.priceUsd);
    if (price > 0) out[a] = { price, h24: num(p.priceChange?.h24), h1: num(p.priceChange?.h1) };
  });

  return NextResponse.json(
    { prices: out },
    { headers: { "Cache-Control": "s-maxage=25, stale-while-revalidate=60" } }
  );
}
