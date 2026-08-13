import { NextResponse } from "next/server";
import { kolLeaderboard } from "@/lib/kol";

export const dynamic = "force-dynamic";

// KOL leaderboard — track record of X handles surfaced through the social
// worker. Empty until the worker (XREACH_URL) is connected and posts have been
// ingested; nothing here is fabricated.
export async function GET() {
  try {
    const kols = await kolLeaderboard();
    return NextResponse.json({ kols });
  } catch {
    return NextResponse.json({ kols: [], error: "read failed" }, { status: 502 });
  }
}
