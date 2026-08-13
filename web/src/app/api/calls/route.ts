import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Call ledger — who surfaced a contract, at what market cap, and how it did
// since. This builds a real track record inside a user's own circle. Ingest
// is a webhook: point a Telegram group / Make / Zapier at POST /api/calls with
// { ca, caller, source } (optionally a shared secret) and every call is
// auto-enriched with its market cap at call time. First-caller wins attribution.

const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;
const INGEST_SECRET = process.env.CALLS_INGEST_SECRET; // optional webhook guard

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

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

interface CallRecord {
  ca: string;
  symbol: string;
  firstCaller: string; // handle/name of whoever called it first
  source: string; // where it came from (group name, "manual", etc.)
  callMcap: number;
  callAt: number;
  peakMcap: number;
  lastMcap: number;
  updatedAt: number;
}

export interface CallStat {
  ca: string;
  symbol: string;
  firstCaller: string;
  source: string;
  callMcap: number;
  callAt: number;
  peakMultiple: number;
  currentMultiple: number;
  ageHours: number;
}

async function enrich(ca: string): Promise<{ symbol: string; mcap: number } | null> {
  try {
    const res = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${ca}`, { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    const sol = (data?.pairs ?? []).filter((p: { chainId?: string }) => p.chainId === "solana");
    if (!sol.length) return null;
    const best = sol.reduce((a: { volume?: { h24?: number } }, b: { volume?: { h24?: number } }) =>
      num(a.volume?.h24) >= num(b.volume?.h24) ? a : b);
    return { symbol: best.baseToken?.symbol ?? "?", mcap: num(best.marketCap) || num(best.fdv) };
  } catch {
    return null;
  }
}

async function getRecord(ca: string): Promise<CallRecord | null> {
  const raw = (await kv(["GET", `mi:call:${ca}`])) as string | null;
  if (!raw) return null;
  try { return JSON.parse(raw) as CallRecord; } catch { return null; }
}

function statOf(r: CallRecord): CallStat {
  return {
    ca: r.ca,
    symbol: r.symbol,
    firstCaller: r.firstCaller,
    source: r.source,
    callMcap: r.callMcap,
    callAt: r.callAt,
    peakMultiple: r.callMcap > 0 ? Number((r.peakMcap / r.callMcap).toFixed(2)) : 1,
    currentMultiple: r.callMcap > 0 ? Number((r.lastMcap / r.callMcap).toFixed(2)) : 1,
    ageHours: Number(((Date.now() - r.callAt) / 3_600_000).toFixed(1)),
  };
}

// POST — ingest a call. Webhook or manual. First caller is recorded once;
// later hits only update peak/last market cap.
export async function POST(req: NextRequest) {
  if (!KV_URL) return NextResponse.json({ error: "kv not configured" }, { status: 503 });
  let body: { ca?: string; caller?: string; source?: string; secret?: string } = {};
  try { body = await req.json(); } catch { /* empty */ }

  if (INGEST_SECRET && body.secret !== INGEST_SECRET) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const ca = (body.ca ?? "").trim();
  if (!/^[A-Za-z0-9]{30,50}$/.test(ca)) {
    return NextResponse.json({ error: "invalid contract address" }, { status: 400 });
  }
  const caller = (body.caller ?? "anon").toString().slice(0, 40);
  const source = (body.source ?? "manual").toString().slice(0, 40);

  const enriched = await enrich(ca);
  if (!enriched) return NextResponse.json({ error: "could not resolve token (not on DexScreener yet?)" }, { status: 404 });

  const now = Date.now();
  const existing = await getRecord(ca);
  if (existing) {
    existing.peakMcap = Math.max(existing.peakMcap, enriched.mcap);
    existing.lastMcap = enriched.mcap;
    existing.updatedAt = now;
    await kv(["SET", `mi:call:${ca}`, JSON.stringify(existing)]);
    return NextResponse.json({ ok: true, firstCaller: existing.firstCaller, alreadyCalled: true, stat: statOf(existing) });
  }

  const rec: CallRecord = {
    ca, symbol: enriched.symbol, firstCaller: caller, source,
    callMcap: enriched.mcap || 1, callAt: now,
    peakMcap: enriched.mcap, lastMcap: enriched.mcap, updatedAt: now,
  };
  await kv(["SET", `mi:call:${ca}`, JSON.stringify(rec)]);
  await kv(["SADD", "mi:calls:index", ca]);
  return NextResponse.json({ ok: true, firstCaller: caller, alreadyCalled: false, stat: statOf(rec) });
}

// GET — the call ledger, refreshed. Optionally refresh market caps on read.
export async function GET() {
  if (!KV_URL) return NextResponse.json({ error: "kv not configured", calls: [] }, { status: 200 });
  try {
    const members = ((await kv(["SMEMBERS", "mi:calls:index"])) as string[] | null) ?? [];
    const stats: CallStat[] = [];
    for (const ca of members.slice(0, 60)) {
      const rec = await getRecord(ca);
      if (rec) stats.push(statOf(rec));
    }
    stats.sort((a, b) => b.callAt - a.callAt);
    return NextResponse.json({ calls: stats });
  } catch {
    return NextResponse.json({ error: "read failed", calls: [] }, { status: 502 });
  }
}
