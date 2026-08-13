import { NextResponse } from "next/server";
import { marketStructure, type Candle } from "@/lib/ta";

export const dynamic = "force-dynamic";

// Real BTC/ETH/SOL market-structure read for the regime dial. Uses Binance
// public daily klines (no key). Cached at the edge for 10 minutes. If Binance
// is unreachable, returns available:false and the client falls back to the
// breadth-derived proxy — the regime never hard-depends on this.

const SYMBOLS = [
  { sym: "BTC", pair: "BTCUSDT" },
  { sym: "ETH", pair: "ETHUSDT" },
  { sym: "SOL", pair: "SOLUSDT" },
];

async function closes(pair: string): Promise<Candle[] | null> {
  try {
    const res = await fetch(
      `https://api.binance.com/api/v3/klines?symbol=${pair}&interval=1d&limit=22`,
      { cache: "no-store", signal: AbortSignal.timeout(6000) }
    );
    if (!res.ok) return null;
    const rows = (await res.json()) as unknown[][];
    // kline: [openTime, open, high, low, close, volume, ...]
    return rows.map((r) => ({
      o: Number(r[1]), h: Number(r[2]), l: Number(r[3]), c: Number(r[4]), v: Number(r[5]),
    }));
  } catch {
    return null;
  }
}

export async function GET() {
  const results = await Promise.all(
    SYMBOLS.map(async (s) => {
      const c = await closes(s.pair);
      if (!c) return { sym: s.sym, state: "UNKNOWN" as const, up: false };
      const st = marketStructure(c, "wick"); // majors are liquid — wicks are real
      const up = st.state === "UPTREND" || st.state === "REVERSAL FORMING";
      return { sym: s.sym, state: st.state, up, detail: st.detail };
    })
  );

  const known = results.filter((r) => r.state !== "UNKNOWN");
  if (!known.length) {
    return NextResponse.json({ available: false, majors: [], majorsUp: null });
  }
  const majorsUp = known.filter((r) => r.up).length;
  return NextResponse.json(
    { available: true, majors: results, majorsUp },
    { headers: { "Cache-Control": "s-maxage=600, stale-while-revalidate=1200" } }
  );
}
