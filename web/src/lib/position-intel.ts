// Slim cross-feed intel for OPEN POSITIONS. The positions view only needs four
// booleans (creator selling / structure broke down / vamp risk / cluster
// dumping) to fire thesis-invalidation alerts — it doesn't need the full safety
// report. This computes just those, reusing a cached full report when one
// exists (zero provider calls) and otherwise doing the minimum targeted work,
// skipping the expensive Rugcheck-full / DAS / holder-tracing / botted / fee
// pieces the full route does.

import { kv } from "@/lib/kv";
import { analyzeChart } from "@/lib/ta";
import { buildCollision, narrativeKeyword } from "@/modules/memecoin/detectors";
import type { DexPair } from "@/types";

const HELIUS_KEY = process.env.HELIUS_API_KEY ?? "8292769f-aeb2-471c-af1d-fb98576972e4";
const BIRDEYE_KEY = process.env.BIRDEYE_API_KEY ?? "dac9521a4c004f65897b2bd3e52cf10d";

export interface PositionIntel {
  creatorDistributing: boolean;
  downtrend: boolean;
  vampRisk: boolean;
  clusterReducing: boolean;
  events: string[];
}

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

function eventsOf(x: Omit<PositionIntel, "events">): string[] {
  const e: string[] = [];
  if (x.creatorDistributing) e.push("The creator wallet is distributing (selling).");
  if (x.downtrend) e.push("Market structure just broke down to a downtrend.");
  if (x.vampRisk) e.push("A vamp risk appeared — a better-named competitor is threatening the narrative.");
  if (x.clusterReducing) e.push("A funding cluster is reducing (coordinated selling).");
  return e;
}

// ── Fast path: derive from a cached full safety report (no provider calls) ──

interface CachedReport {
  creator?: { status?: string };
  chart?: { structure?: { state?: string } };
  collision?: { vampRisk?: boolean };
  deep?: { clusterTrend?: string | null };
}
function fromReport(r: CachedReport): PositionIntel {
  const x = {
    creatorDistributing: r.creator?.status === "distributing",
    downtrend: r.chart?.structure?.state === "DOWNTREND",
    vampRisk: !!r.collision?.vampRisk,
    clusterReducing: !!(r.deep?.clusterTrend && String(r.deep.clusterTrend).startsWith("⚠")),
  };
  return { ...x, events: eventsOf(x) };
}

// ── Minimal provider fetchers (only what the light path needs) ─────────────

async function getOhlcv(mint: string): Promise<{ o: number; h: number; l: number; c: number; v: number }[]> {
  try {
    const now = Math.floor(Date.now() / 1000);
    const from = now - 60 * 60 * 24 * 2;
    const res = await fetch(
      `https://public-api.birdeye.so/defi/ohlcv?address=${mint}&type=15m&time_from=${from}&time_to=${now}`,
      { headers: { "X-API-KEY": BIRDEYE_KEY, "x-chain": "solana" }, cache: "no-store" }
    );
    if (!res.ok) return [];
    const data = await res.json();
    const items = data?.data?.items ?? [];
    return items.map((c: Record<string, unknown>) => ({ o: num(c.o), h: num(c.h), l: num(c.l), c: num(c.c), v: num(c.v) }));
  } catch {
    return [];
  }
}

async function getDexPair(mint: string): Promise<DexPair | null> {
  try {
    const res = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${mint}`, { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    const sol = (data.pairs ?? []).filter((p: { chainId?: string }) => p.chainId === "solana");
    if (!sol.length) return null;
    return sol.reduce((a: { volume?: { h24?: number } }, b: { volume?: { h24?: number } }) =>
      num(a.volume?.h24) >= num(b.volume?.h24) ? a : b) as DexPair;
  } catch {
    return null;
  }
}

async function searchNarrative(keyword: string): Promise<DexPair[]> {
  try {
    const res = await fetch(`https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(keyword)}`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return (data?.pairs ?? []) as DexPair[];
  } catch {
    return [];
  }
}

async function resolveCreator(mint: string): Promise<string | null> {
  try {
    const res = await fetch(`https://api.rugcheck.xyz/v1/tokens/${mint}/report/summary`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    const data = await res.json();
    return (data?.creator as string) ?? null;
  } catch {
    return null;
  }
}

interface TokenAccResp {
  value?: { account?: { data?: { parsed?: { info?: { tokenAmount?: { uiAmount?: number } } } } } }[];
}
async function creatorBalance(owner: string, mint: string): Promise<number | null> {
  try {
    const res = await fetch(`https://mainnet.helius-rpc.com/?api-key=${HELIUS_KEY}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "getTokenAccountsByOwner", params: [owner, { mint }, { encoding: "jsonParsed" }] }),
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    const value: TokenAccResp["value"] = data?.result?.value ?? [];
    let sum = 0;
    for (const acc of value ?? []) {
      const ui = acc?.account?.data?.parsed?.info?.tokenAmount?.uiAmount;
      if (typeof ui === "number") sum += ui;
    }
    return sum;
  } catch {
    return null;
  }
}

// ── Entry point ─────────────────────────────────────────────────────────────

export async function getPositionIntel(mint: string): Promise<PositionIntel> {
  // 1. Reuse a cached full safety report if present — zero provider calls.
  const cached = (await kv(["GET", `mi:safety:${mint}`])) as string | null;
  if (cached) {
    try {
      return fromReport(JSON.parse(cached) as CachedReport);
    } catch {
      /* fall through to light compute */
    }
  }

  // 2. Light compute — structure + vamp + creator-selling only.
  const [ohlcv, dex] = await Promise.all([getOhlcv(mint), getDexPair(mint)]);

  let downtrend = false;
  if (ohlcv.length >= 12) {
    const ageHours = dex?.pairCreatedAt ? (Date.now() - dex.pairCreatedAt) / 3_600_000 : 0;
    downtrend = analyzeChart(ohlcv, ageHours, "body").structure.state === "DOWNTREND";
  }

  let vampRisk = false;
  if (dex) {
    const kw = narrativeKeyword(dex.baseToken?.symbol ?? "", dex.baseToken?.name ?? "");
    if (kw && kw.length > 2) {
      const pairs = await searchNarrative(kw);
      if (pairs.length) {
        vampRisk = buildCollision(kw, { symbol: dex.baseToken?.symbol ?? "", address: mint }, pairs).vampRisk;
      }
    }
  }

  let creatorDistributing = false;
  const creator = await resolveCreator(mint);
  if (creator) {
    const bal = await creatorBalance(creator, mint);
    if (bal !== null) {
      const snapRaw = (await kv(["GET", `mi:cbal:${mint}`])) as string | null;
      let prev: { bal: number; at: number } | null = null;
      try { prev = snapRaw ? JSON.parse(snapRaw) : null; } catch { prev = null; }
      if (prev && prev.bal > 0 && (bal - prev.bal) / prev.bal < -0.05) creatorDistributing = true;
      await kv(["SET", `mi:cbal:${mint}`, JSON.stringify({ bal, at: Date.now() }), "EX", 7 * 86400]);
    }
  }

  const x = { creatorDistributing, downtrend, vampRisk, clusterReducing: false };
  return { ...x, events: eventsOf(x) };
}
