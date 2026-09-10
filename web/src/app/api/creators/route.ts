import { NextRequest, NextResponse } from "next/server";
import { kvConfigured } from "@/lib/kv";
import { creatorLeaderboard, creatorStatsFor, ingestCreators } from "@/lib/creator-ledger";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

// POST: ingest tokens {mint, symbol, mcap}[]. Kept for compatibility, but the
// shared scan now ingests server-side on every cycle (see /api/scan), so the
// ledger grows regardless of who's viewing the Creators tab.
export async function POST(req: NextRequest) {
  if (!kvConfigured()) return NextResponse.json({ error: "storage not configured" }, { status: 503 });
  try {
    const body = await req.json();
    const tokens: { mint: string; symbol: string; mcap: number }[] = body?.tokens ?? [];
    const ingested = await ingestCreators(tokens);
    return NextResponse.json({ ok: true, ingested });
  } catch {
    return NextResponse.json({ error: "ingest failed" }, { status: 502 });
  }
}

// GET: leaderboard of tracked creators, or ?creator=addr for one record.
export async function GET(req: NextRequest) {
  if (!kvConfigured()) return NextResponse.json({ error: "storage not configured", creators: [] }, { status: 200 });
  const single = new URL(req.url).searchParams.get("creator");
  try {
    if (single) {
      return NextResponse.json({ stats: await creatorStatsFor(single) });
    }
    return NextResponse.json(
      { creators: await creatorLeaderboard() },
      { headers: { "Cache-Control": "s-maxage=120, stale-while-revalidate=300" } }
    );
  } catch {
    return NextResponse.json({ error: "read failed", creators: [] }, { status: 502 });
  }
}
