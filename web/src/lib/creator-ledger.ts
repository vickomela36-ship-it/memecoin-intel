// Creator ledger — a shared, persistent record of deployer wallets and how
// their tokens perform, accumulated from tokens the scanner surfaces. Stored in
// Postgres (see lib/kv). Extracted here so BOTH the /api/creators route and the
// shared scan can ingest — the ledger now grows on every scan cycle, not only
// when someone opens the Creators tab.

import { kv, kvMGet } from "@/lib/kv";

export interface TokenRecord {
  mint: string;
  symbol: string;
  firstSeenMcap: number;
  firstSeenAt: number;
  peakMcap: number;
  lastMcap: number;
  updatedAt: number;
}

export interface CreatorRecord {
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
  hits: number;
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

export function computeStats(rec: CreatorRecord): CreatorStats {
  const now = Date.now();
  const tokens = rec.tokens;
  const multiples = tokens.map((t) => (t.firstSeenMcap > 0 ? t.peakMcap / t.firstSeenMcap : 1));
  const hits = multiples.filter((m) => m >= 2).length;
  const bestMultiple = multiples.length ? Math.max(...multiples) : 1;
  const avgPeak = multiples.length ? multiples.reduce((a, b) => a + b, 0) / multiples.length : 1;
  const hitRate = tokens.length ? hits / tokens.length : 0;

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

export async function getRecord(creator: string): Promise<CreatorRecord | null> {
  const raw = (await kv(["GET", `mi:creator:${creator}`])) as string | null;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CreatorRecord;
  } catch {
    return null;
  }
}

/** Resolve a token's creator via Rugcheck (cheap, 1h-cached). */
export async function resolveCreator(mint: string): Promise<string | null> {
  try {
    const res = await fetch(`https://api.rugcheck.xyz/v1/tokens/${mint}/report/summary`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const data = await res.json();
      if (data?.creator) return data.creator as string;
    }
  } catch {
    /* ignore */
  }
  return null;
}

/**
 * Ingest tokens into the ledger — resolve creators, upsert records, update peak
 * mcaps. Per-token 30-min dedup marker keeps repeat scans cheap. Returns how
 * many NEW tokens were recorded.
 */
export async function ingestCreators(
  tokens: { mint: string; symbol: string; mcap: number }[]
): Promise<number> {
  let ingested = 0;
  const now = Date.now();
  for (const t of tokens.slice(0, 12)) {
    if (!/^[A-Za-z0-9]{30,50}$/.test(t.mint)) continue;
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
    rec.tokens = rec.tokens.slice(-40);
    rec.updatedAt = now;
    await kv(["SET", `mi:creator:${creator}`, JSON.stringify(rec)]);
    await kv(["SADD", "mi:creators:index", creator]);
  }
  return ingested;
}

export async function creatorStatsFor(creator: string): Promise<CreatorStats | null> {
  const rec = await getRecord(creator);
  return rec ? computeStats(rec) : null;
}

export async function creatorLeaderboard(): Promise<CreatorStats[]> {
  const members = ((await kv(["SMEMBERS", "mi:creators:index"])) as string[] | null) ?? [];
  const recordMap = await kvMGet(members.slice(0, 100).map((c) => `mi:creator:${c}`));
  const stats: CreatorStats[] = [];
  for (const raw of Array.from(recordMap.values())) {
    let rec: CreatorRecord | null = null;
    try { rec = JSON.parse(raw) as CreatorRecord; } catch { continue; }
    if (rec && rec.tokens.length) stats.push(computeStats(rec));
  }
  const rank: Record<CreatorCategory, number> = {
    PROVEN: 0, SERIAL: 1, "ONE-HIT": 2, COOKING: 3, "RUG-PRONE": 4, NEW: 5,
  };
  stats.sort((a, b) => rank[a.category] - rank[b.category] || b.bestMultiple - a.bestMultiple);
  return stats.slice(0, 50);
}
