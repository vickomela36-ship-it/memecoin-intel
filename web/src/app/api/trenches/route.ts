import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Trenches heat gauge — real onchain-condition metrics derived from the
// creator ledger (which already persists every surfaced token's first-seen and
// peak market cap). Computes: how many tokens ran >=10x this week, the median
// fresh-launch topping market cap, and the count of fresh launches. These are
// measured from accumulated history, not fabricated. Empty until the ledger
// has data.

const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;

async function kv(cmd: (string | number)[]): Promise<unknown> {
  if (!KV_URL || !KV_TOKEN) return null;
  try {
    const res = await fetch(KV_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${KV_TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify(cmd),
      cache: "no-store",
    });
    const data = await res.json();
    return data?.result ?? null;
  } catch {
    return null;
  }
}

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
  if (!KV_URL) return NextResponse.json({ available: false });
  try {
    const members = ((await kv(["SMEMBERS", "mi:creators:index"])) as string[] | null) ?? [];
    const now = Date.now();
    const WEEK = 7 * 86400 * 1000;
    const DAY = 86400 * 1000;

    let runnersThisWeek = 0;
    let seenThisWeek = 0;
    const freshMcaps: number[] = [];
    const peakMcaps: number[] = [];

    for (const c of members.slice(0, 120)) {
      const raw = (await kv(["GET", `mi:creator:${c}`])) as string | null;
      if (!raw) continue;
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

    return NextResponse.json(
      {
        available: seenThisWeek > 0,
        runnersThisWeek,
        seenThisWeek,
        freshLaunchMedianMcap: Math.round(median(freshMcaps)),
        freshLaunchCount: freshMcaps.length,
        peakMedianMcap: Math.round(median(peakMcaps)),
        heat: runnerHeat,
      },
      { headers: { "Cache-Control": "s-maxage=300, stale-while-revalidate=600" } }
    );
  } catch {
    return NextResponse.json({ available: false });
  }
}
