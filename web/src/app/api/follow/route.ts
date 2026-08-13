import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Follow-don't-copy: surface what a tracked wallet has been BUYING as an
// information stream — explicitly NOT a buy signal. Uses Helius enhanced
// transactions (parsed SWAPs). The consumer UI carries the abuse-pattern
// warning: a followed trader can buy on private wallets first, then make a
// small visible buy to trigger followers who provide exit liquidity.

const HELIUS_KEY =
  process.env.HELIUS_API_KEY ?? "8292769f-aeb2-471c-af1d-fb98576972e4";

const STABLES = new Set([
  "So11111111111111111111111111111111111111112", // wSOL
  "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", // USDC
  "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", // USDT
]);

interface TokenTransfer {
  fromUserAccount?: string;
  toUserAccount?: string;
  mint?: string;
  tokenAmount?: number;
}
interface EnhancedTx {
  timestamp?: number;
  description?: string;
  type?: string;
  tokenTransfers?: TokenTransfer[];
}

export async function GET(req: NextRequest) {
  const addr = new URL(req.url).searchParams.get("addr");
  if (!addr || !/^[A-Za-z0-9]{32,44}$/.test(addr)) {
    return NextResponse.json({ error: "invalid wallet address" }, { status: 400 });
  }

  try {
    const res = await fetch(
      `https://api.helius.xyz/v0/addresses/${addr}/transactions?api-key=${HELIUS_KEY}&type=SWAP&limit=15`,
      { cache: "no-store" }
    );
    if (!res.ok) {
      return NextResponse.json({ error: `helius ${res.status}`, buys: [] }, { status: 502 });
    }
    const txs = (await res.json()) as EnhancedTx[];
    const buys: { mint: string; amount: number; ts: number; description: string }[] = [];
    for (const tx of txs ?? []) {
      // A "buy" = the wallet RECEIVED a non-stable token in this swap.
      const got = (tx.tokenTransfers ?? []).find(
        (t) => t.toUserAccount === addr && t.mint && !STABLES.has(t.mint)
      );
      if (got?.mint) {
        buys.push({
          mint: got.mint,
          amount: Number(got.tokenAmount) || 0,
          ts: (tx.timestamp ?? 0) * 1000,
          description: (tx.description ?? "").slice(0, 140),
        });
      }
      if (buys.length >= 8) break;
    }
    return NextResponse.json({ addr, buys });
  } catch {
    return NextResponse.json({ error: "wallet activity unreachable", buys: [] }, { status: 502 });
  }
}
