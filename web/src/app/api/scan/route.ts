import { NextResponse } from "next/server";
import { cachedScan } from "@/lib/scan-cache";
import { kv } from "@/lib/kv";
import { ingestCreators } from "@/lib/creator-ledger";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await cachedScan();

    // Grow the creator ledger from the scan itself — once per ~60s across all
    // traffic (a 60s NX lock), so it accumulates regardless of who's viewing
    // the Creators tab. Whoever wins the lock does the (dedup-throttled) ingest;
    // everyone else skips instantly. Best-effort — never blocks the scan on error.
    try {
      const gotLock = await kv(["SET", "mi:creator-ingest-lock", "1", "EX", 60, "NX"]);
      if (gotLock === "OK") {
        const tokens = [...(result.launches ?? []), ...(result.pumpfun ?? [])].map((s) => ({
          mint: s.address, symbol: s.symbol, mcap: s.fdv,
        }));
        if (tokens.length) await ingestCreators(tokens);
      }
    } catch {
      /* ingest is best-effort; the scan response must not depend on it */
    }

    // The scan data refreshes every 60s (cachedScan). Let Vercel's edge serve
    // that same window so repeat loads/refreshes don't each invoke the function.
    return NextResponse.json(result, {
      headers: { "Cache-Control": "s-maxage=60, stale-while-revalidate=120" },
    });
  } catch {
    return NextResponse.json({ error: "scan failed" }, { status: 502 });
  }
}
