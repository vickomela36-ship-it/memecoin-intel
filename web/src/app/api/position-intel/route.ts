import { NextRequest, NextResponse } from "next/server";
import { getPositionIntel } from "@/lib/position-intel";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Slim per-position cross-feed intel — the four thesis-invalidation booleans
// the positions view needs, without the full safety-report cost. Reuses a
// cached full report when one exists. Edge-cached so several viewers tracking
// the same token share one computation.
export async function GET(req: NextRequest) {
  const mint = new URL(req.url).searchParams.get("mint");
  if (!mint || !/^[A-Za-z0-9]{30,50}$/.test(mint)) {
    return NextResponse.json({ error: "bad mint", events: [] }, { status: 400 });
  }
  try {
    const intel = await getPositionIntel(mint);
    return NextResponse.json(intel, {
      headers: { "Cache-Control": "s-maxage=120, stale-while-revalidate=300" },
    });
  } catch {
    return NextResponse.json({ error: "intel failed", events: [] }, { status: 502 });
  }
}
