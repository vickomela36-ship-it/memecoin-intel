import { NextResponse } from "next/server";
import { kv, kvConfigured, kvMGet } from "@/lib/kv";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Trenches heat gauge — real onchain-condition metrics derived from the
// creator ledger (which already persists every surfaced token's first-seen and
// peak market cap). Computes: how many tokens ran >=10x this week, the median
// fresh-launch topping market cap, and the count of fresh launches. These are
// measured from accumulated history, not fabricated. Empty until the ledger
// has data.


interface TokenRecord {
  firstSeenMcap: number;
  firstSeenAt: number;
  peakMcap: number;
}
interface CreatorRecord { tokens: TokenRecord[] }

function median(xs: number[]): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
}

export async function GET() {
  if (!kvConfigured()) return NextResponse.json({ available: false });
  try {
    const members = ((await kv(["SMEMBERS", "mi:creators:index"])) as string[] | null) ?? [];
    const now = Date.now();
    const WEEK = 7 * 86400 * 1000;
    const DAY = 86400 * 1000;

    let runnersThisWeek = 0;
    let seenThisWeek = 0;
    const freshMcaps: number[] = [];
    const peakMcaps: number[] = [];

    // Batched fetch — one query for all creator records instead of 120 GETs.
    const recordMap = await kvMGet(members.slice(0, 120).map((c) => `mi:creator:${c}`));
    for (const raw of Array.from(recordMap.values())) {
      let rec: CreatorRecord | null = null;
      try { rec = JSON.parse(raw) as CreatorRecord; } catch { continue; }
      for (const t of rec.tokens ?? []) {
        if (now - t.firstSeenAt <= WEEK) {
          seenThisWeek++;
          if (t.firstSeenMcap > 0 && t.peakMcap / t.firstSeenMcap >= 10) runnersThisWeek++;
          peakMcaps.push(t.peakMcap);
        }
        if (now - t.firstSeenAt <= DAY && t.firstSeenMcap > 0) freshMcaps.push(t.firstSeenMcap);
      }
    }

    // 0-3 heat proxy blending runners and how hot fresh launches are topping.
    const runnerHeat = runnersThisWeek >= 8 ? 3 : runnersThisWeek >= 3 ? 2 : runnersThisWeek >= 1 ? 1 : 0;

    // Graduation rate from the PumpPortal WS sampler (rolling 24h of samples).
    // gradRate = migrations / new tokens across the window — a real launchpad
    // heat metric. Null when no samples have been collected yet.
    let gradRate: number | null = null;
    let gradSamples = 0;
    try {
      const raw = (await kv(["GET", "mi:grad:samples"])) as string | null;
      const series: { at: number; newTokens: number; migrations: number }[] = raw ? JSON.parse(raw) : [];
      const recent = series.filter((s) => now - s.at <= DAY);
      const nTok = recent.reduce((s, r) => s + (r.newTokens || 0), 0);
      const nMig = recent.reduce((s, r) => s + (r.migrations || 0), 0);
      gradSamples = recent.length;
      if (nTok > 0) gradRate = Number(((nMig / nTok) * 100).toFixed(2));
    } catch {
      /* no graduation data yet */
    }

    return NextResponse.json(
      {
        available: seenThisWeek > 0 || gradSamples > 0,
        runnersThisWeek,
        seenThisWeek,
        freshLaunchMedianMcap: Math.round(median(freshMcaps)),
        freshLaunchCount: freshMcaps.length,
        peakMedianMcap: Math.round(median(peakMcaps)),
        heat: runnerHeat,
        graduationRate: gradRate,
        graduationSamples: gradSamples,
      },
      { headers: { "Cache-Control": "s-maxage=300, stale-while-revalidate=600" } }
    );
  } catch {
    return NextResponse.json({ available: false });
  }
}
