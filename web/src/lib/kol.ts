// KOL track-record ledger. Persists, per X handle, every token they posted
// about — market cap at post time and how it did since. This lets the tool
// answer "is this person actually right, or do they post near local tops with
// no reasoning?" over time. Data only ever comes from the configured social
// worker; nothing is fabricated. Dormant (no-ops) when KV is unset.

const KV_URL = process.env.KV_REST_API_URL ?? process.env.UPSTASH_REDIS_REST_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN ?? process.env.UPSTASH_REDIS_REST_TOKEN;

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

interface KolCall {
  ca: string;
  symbol: string;
  mcapAtPost: number;
  postAt: number;
  peakMcap: number;
  lastMcap: number;
  hadThesis: boolean;
}
interface KolRecord {
  handle: string;
  calls: KolCall[];
  updatedAt: number;
}

export interface KolStat {
  handle: string;
  callCount: number;
  hitRate: number; // fraction of calls that >=2x'd from post
  avgPeakMultiple: number;
  noReasoningRatio: number; // fraction of calls with no thesis
  nearTopRatio: number; // fraction that fell below post mcap (posted near tops)
  grade: "SHARP" | "MIXED" | "FADE" | "NEW";
  recent: { symbol: string; ca: string; peakMultiple: number; hadThesis: boolean }[];
}

async function getRecord(handle: string): Promise<KolRecord | null> {
  const raw = (await kv(["GET", `mi:kol:${handle.toLowerCase()}`])) as string | null;
  if (!raw) return null;
  try { return JSON.parse(raw) as KolRecord; } catch { return null; }
}

/** Ingest the human posters for a token as "calls" at the current market cap. */
export async function ingestKolPosts(
  ca: string,
  symbol: string,
  mcap: number,
  posters: { handle: string; hadThesis: boolean }[]
): Promise<void> {
  if (!KV_URL || mcap <= 0) return;
  const now = Date.now();
  // De-dupe posters by handle within this ingest.
  const seen = new Set<string>();
  for (const p of posters) {
    const handle = p.handle.toLowerCase();
    if (!handle || seen.has(handle)) continue;
    seen.add(handle);

    const rec = (await getRecord(handle)) ?? { handle, calls: [], updatedAt: now };
    const existing = rec.calls.find((c) => c.ca === ca);
    if (existing) {
      existing.peakMcap = Math.max(existing.peakMcap, mcap);
      existing.lastMcap = mcap;
    } else {
      rec.calls.push({ ca, symbol, mcapAtPost: mcap || 1, postAt: now, peakMcap: mcap, lastMcap: mcap, hadThesis: p.hadThesis });
    }
    rec.calls = rec.calls.slice(-50);
    rec.updatedAt = now;
    await kv(["SET", `mi:kol:${handle}`, JSON.stringify(rec)]);
    await kv(["SADD", "mi:kols:index", handle]);
  }
}

function statOf(rec: KolRecord): KolStat {
  const calls = rec.calls;
  const mults = calls.map((c) => (c.mcapAtPost > 0 ? c.peakMcap / c.mcapAtPost : 1));
  const hits = mults.filter((m) => m >= 2).length;
  const noReason = calls.filter((c) => !c.hadThesis).length;
  const nearTop = calls.filter((c) => c.lastMcap < c.mcapAtPost).length;
  const hitRate = calls.length ? hits / calls.length : 0;
  const noReasoningRatio = calls.length ? noReason / calls.length : 0;
  const nearTopRatio = calls.length ? nearTop / calls.length : 0;
  const avgPeak = mults.length ? mults.reduce((a, b) => a + b, 0) / mults.length : 1;

  let grade: KolStat["grade"];
  if (calls.length < 3) grade = "NEW";
  else if (hitRate >= 0.4 && noReasoningRatio < 0.5) grade = "SHARP";
  else if (nearTopRatio > 0.55 || noReasoningRatio > 0.7) grade = "FADE";
  else grade = "MIXED";

  return {
    handle: rec.handle,
    callCount: calls.length,
    hitRate: Number(hitRate.toFixed(2)),
    avgPeakMultiple: Number(avgPeak.toFixed(2)),
    noReasoningRatio: Number(noReasoningRatio.toFixed(2)),
    nearTopRatio: Number(nearTopRatio.toFixed(2)),
    grade,
    recent: [...calls].sort((a, b) => b.postAt - a.postAt).slice(0, 5).map((c) => ({
      symbol: c.symbol, ca: c.ca,
      peakMultiple: c.mcapAtPost > 0 ? Number((c.peakMcap / c.mcapAtPost).toFixed(2)) : 1,
      hadThesis: c.hadThesis,
    })),
  };
}

export async function kolStats(handle: string): Promise<KolStat | null> {
  const rec = await getRecord(handle);
  return rec && rec.calls.length ? statOf(rec) : null;
}

export async function kolLeaderboard(): Promise<KolStat[]> {
  const members = ((await kv(["SMEMBERS", "mi:kols:index"])) as string[] | null) ?? [];
  const stats: KolStat[] = [];
  for (const h of members.slice(0, 80)) {
    const s = await kolStats(h);
    if (s) stats.push(s);
  }
  const rank: Record<KolStat["grade"], number> = { SHARP: 0, MIXED: 1, NEW: 2, FADE: 3 };
  stats.sort((a, b) => rank[a.grade] - rank[b.grade] || b.hitRate - a.hitRate);
  return stats;
}
