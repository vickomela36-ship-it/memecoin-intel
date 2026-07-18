import { NextResponse } from "next/server";
import { unstable_cache } from "next/cache";
import { buildLpCall, type RawPool } from "@/modules/crypto/lp";
import type { LpCall, LpResult } from "@/types";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Meteora DLMM public API — free, no key. Pull the most active pools,
// classify + attach strategy, group by category. Cached 5 min.
const getLp = unstable_cache(
  async (): Promise<LpResult> => {
    let pools: RawPool[] = [];
    try {
      const res = await fetch(
        "https://dlmm-api.meteora.ag/pair/all_with_pagination?page=0&limit=120&sort_key=volume&order_by=desc&hide_low_tvl=15000",
        { cache: "no-store" }
      );
      if (res.ok) {
        const data = await res.json();
        pools = (data?.pairs ?? data ?? []) as RawPool[];
      }
    } catch {
      /* fall through to empty */
    }

    const calls: LpCall[] = [];
    const seen = new Set<string>();
    for (const p of pools) {
      const call = buildLpCall(p);
      if (!call) continue;
      // Keep the best pool per pair name (dedupe across bin steps)
      const key = call.name;
      if (seen.has(key)) continue;
      seen.add(key);
      calls.push(call);
    }

    const byQuality = (a: LpCall, b: LpCall) => b.quality - a.quality;
    return {
      stable: calls.filter((c) => c.cls === "STABLE").sort(byQuality).slice(0, 6),
      bluechip: calls.filter((c) => c.cls === "BLUECHIP").sort(byQuality).slice(0, 8),
      memecoin: calls.filter((c) => c.cls === "MEMECOIN").sort(byQuality).slice(0, 10),
      fetchedAt: Date.now(),
      poolsScanned: pools.length,
    };
  },
  ["lp-calls-v1"],
  { revalidate: 300 }
);

export async function GET() {
  try {
    return NextResponse.json(await getLp());
  } catch {
    return NextResponse.json({ error: "meteora unreachable" }, { status: 502 });
  }
}
