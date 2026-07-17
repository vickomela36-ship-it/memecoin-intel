import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

// Creator ledger — a shared, persistent record of deployer wallets and how
// their tokens perform. Built up over time from tokens the scanner surfaces.
// Stored in KV so it accumulates across all sessions and devices.

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
  mint: string;
  symbol: string;
  firstSeenMcap: number;
  firstSeenAt: number;
  peakMcap: number;
  lastMcap: number;
  updatedAt: number;
}

interface CreatorRecord {
  creator: string;
  tokens: TokenRecord[];
  updatedAt: number;
}

export type CreatorCategory =
  | "PROVEN"
  | "SERIAL"
  | "ONE-HIT"
  | "RUG-PRONE"
  | "COOKING"
  | "NEW";

export interface CreatorStats {
  creator: string;
  tokenCount: number;
  hits: number; // tokens that >=2x'd from first-seen mcap
  bestMultiple: number;
  avgPeakMultiple: number;
  hitRate: number;
  category: CreatorCategory;
  recentTokens: { symbol: string; mint: string; peakMultiple: number; ageHours: number }[];
}

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

function computeStats(rec: CreatorRecord): CreatorStats {
  const now = Date.now();
  const tokens = rec.tokens;
  const multiples = tokens.map((t) =>
    t.firstSeenMcap > 0 ? t.peakMcap / t.firstSeenMcap : 1
  );
  const hits = multiples.filter((m) => m >= 2).length;
  const bestMultiple = multiples.length ? Math.max(...multiples) : 1;
  const avgPeak = multiples.length ? multiples.reduce((a, b) => a + b, 0) / multiples.length : 1;
  const hitRate = tokens.length ? hits / tokens.length : 0;

  // Died = peaked barely above entry then round-tripped below it
  const died = tokens.filter(
    (t) => t.firstSeenMcap > 0 && t.peakMcap / t.firstSeenMcap < 1.3 && t.lastMcap < t.firstSeenMcap * 0.5
  ).length;

  let category: CreatorCategory;
  if (tokens.length >= 2 && hits >= 2 && hitRate >= 0.4) category = "PROVEN";
  else if (tokens.length >= 5 && died / tokens.length > 0.6) category = "RUG-PRONE";
  else if (hits >= 1 && tokens.length <= 3) category = "ONE-HIT";
  else if (tokens.length >= 4) category = "SERIAL";
  else if (tokens.some((t) => now - t.firstSeenAt < 6 * 3600 * 1000)) category = "COOKING";
  else category = "NEW";

  const recentTokens = [...tokens]
    .sort((a, b) => b.firstSeenAt - a.firstSeenAt)
    .slice(0, 5)
    .map((t) => ({
      symbol: t.symbol,
      mint: t.mint,
      peakMultiple: t.firstSeenMcap > 0 ? Number((t.peakMcap / t.firstSeenMcap).toFixed(2)) : 1,
      ageHours: Number(((now - t.firstSeenAt) / 3_600_000).toFixed(1)),
    }));

  return {
    creator: rec.creator,
    tokenCount: tokens.length,
    hits,
    bestMultiple: Number(bestMultiple.toFixed(2)),
    avgPeakMultiple: Number(avgPeak.toFixed(2)),
    hitRate: Number(hitRate.toFixed(2)),
    category,
    recentTokens,
  };
}

async function getRecord(creator: string): Promise<CreatorRecord | null> {
  const raw = (await kv(["GET", `mi:creator:${creator}`])) as string | null;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CreatorRecord;
  } catch {
    return null;
  }
}

// Resolve a token's creator via Rugcheck (cheap, cached).
async function resolveCreator(mint: string): Promise<string | null> {
  try {
    const res = await fetch(`https://api.rugcheck.xyz/v1/tokens/${mint}/report/summary`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const data = await res.json();
      if (data?.creator) return data.creator as string;
    }
    const full = await fetch(`https://api.rugcheck.xyz/v1/tokens/${mint}/report`, {
      next: { revalidate: 3600 },
    });
    if (full.ok) {
      const data = await full.json();
      return (data?.creator as string) ?? null;
    }
  } catch {
    /* ignore */
  }
  return null;
}

// POST: ingest tokens {mint, symbol, mcap}[] — resolve creators, upsert
// records, update peak mcaps. Called by the scanner enrichment step.
export async function POST(req: NextRequest) {
  if (!KV_URL) return NextResponse.json({ error: "kv not configured" }, { status: 503 });
  try {
    const body = await req.json();
    const tokens: { mint: string; symbol: string; mcap: number }[] = (body?.tokens ?? []).slice(0, 12);
    let ingested = 0;
    const now = Date.now();

    for (const t of tokens) {
      if (!/^[A-Za-z0-9]{30,50}$/.test(t.mint)) continue;
      // Skip tokens already logged in the last 30m (dedup via marker key)
      const marker = await kv(["SET", `mi:cseen:${t.mint}`, "1", "EX", 1800, "NX"]);
      const creator = await resolveCreator(t.mint);
      if (!creator) continue;

      const rec = (await getRecord(creator)) ?? { creator, tokens: [], updatedAt: now };
      const existing = rec.tokens.find((x) => x.mint === t.mint);
      const mcap = num(t.mcap);
      if (existing) {
        existing.peakMcap = Math.max(existing.peakMcap, mcap);
        existing.lastMcap = mcap;
        existing.updatedAt = now;
      } else if (marker === "OK") {
        rec.tokens.push({
          mint: t.mint, symbol: t.symbol, firstSeenMcap: mcap || 1,
          firstSeenAt: now, peakMcap: mcap, lastMcap: mcap, updatedAt: now,
        });
        ingested++;
      }
      rec.tokens = rec.tokens.slice(-40); // cap history per creator
      rec.updatedAt = now;
      await kv(["SET", `mi:creator:${creator}`, JSON.stringify(rec)]);
      await kv(["SADD", "mi:creators:index", creator]);
    }
    return NextResponse.json({ ok: true, ingested });
  } catch {
    return NextResponse.json({ error: "ingest failed" }, { status: 502 });
  }
}

// GET: leaderboard of tracked creators, or ?creator=addr for one record.
export async function GET(req: NextRequest) {
  if (!KV_URL) return NextResponse.json({ error: "kv not configured", creators: [] }, { status: 200 });
  const single = new URL(req.url).searchParams.get("creator");
  try {
    if (single) {
      const rec = await getRecord(single);
      return NextResponse.json({ stats: rec ? computeStats(rec) : null });
    }
    const members = ((await kv(["SMEMBERS", "mi:creators:index"])) as string[] | null) ?? [];
    const stats: CreatorStats[] = [];
    for (const c of members.slice(0, 100)) {
      const rec = await getRecord(c);
      if (rec && rec.tokens.length) stats.push(computeStats(rec));
    }
    // Proven + serial first, then by best multiple
    const rank: Record<CreatorCategory, number> = {
      PROVEN: 0, SERIAL: 1, "ONE-HIT": 2, COOKING: 3, "RUG-PRONE": 4, NEW: 5,
    };
    stats.sort((a, b) => rank[a.category] - rank[b.category] || b.bestMultiple - a.bestMultiple);
    return NextResponse.json({ creators: stats.slice(0, 50) });
  } catch {
    return NextResponse.json({ error: "read failed", creators: [] }, { status: 502 });
  }
}
