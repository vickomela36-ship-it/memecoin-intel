import { NextRequest, NextResponse } from "next/server";
import type {
  DexPair,
  FundingCluster,
  SafetyCheck,
  SafetyReport,
  SafetyVerdict,
} from "@/types";
import {
  buildCollision,
  classifyCoinType,
  detectBottedChart,
  narrativeKeyword,
  type OHLCV,
} from "@/modules/memecoin/detectors";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const HELIUS_KEY =
  process.env.HELIUS_API_KEY ?? "8292769f-aeb2-471c-af1d-fb98576972e4";
const BIRDEYE_KEY =
  process.env.BIRDEYE_API_KEY ?? "dac9521a4c004f65897b2bd3e52cf10d";

const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

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

/** fetch with one 429/5xx backoff — the providers are the rate-limit cost. */
async function fetchRetry(url: string, init?: RequestInit, tries = 2): Promise<Response | null> {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, init);
      if (res.status === 429 || res.status >= 500) {
        if (i < tries - 1) {
          await new Promise((r) => setTimeout(r, 600 * (i + 1)));
          continue;
        }
      }
      return res;
    } catch {
      if (i < tries - 1) await new Promise((r) => setTimeout(r, 400));
    }
  }
  return null;
}

async function heliusRpc<T>(method: string, params: unknown[]): Promise<T | null> {
  try {
    const res = await fetch(`https://mainnet.helius-rpc.com/?api-key=${HELIUS_KEY}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    return (data?.result as T) ?? null;
  } catch {
    return null;
  }
}

// ── Provider payloads (partial shapes) ────────────────────────────────────

interface RugReport {
  mint?: string;
  creator?: string;
  mintAuthority?: string | null;
  freezeAuthority?: string | null;
  token?: { supply?: number; decimals?: number };
  score?: number;
  score_normalised?: number;
  totalMarketLiquidity?: number;
  totalHolders?: number;
  markets?: {
    lp?: { lpLockedPct?: number; lpLocked?: number; lpTotalSupply?: number };
    liquidityA?: string;
    liquidityB?: string;
  }[];
  topHolders?: { address?: string; owner?: string; pct?: number; amount?: number; insider?: boolean }[];
  risks?: { name?: string; level?: string }[];
}

interface DexResp {
  pairs?: {
    chainId?: string;
    dexId?: string;
    baseToken?: { symbol?: string; name?: string };
    priceChange?: { h1?: number; h6?: number; h24?: number };
    volume?: { h24?: number };
    liquidity?: { usd?: number };
    fdv?: number;
    marketCap?: number;
    pairCreatedAt?: number;
    quoteToken?: { address?: string };
    pairAddress?: string;
  }[];
}

async function getRugReport(mint: string): Promise<RugReport | null> {
  const res = await fetchRetry(`https://api.rugcheck.xyz/v1/tokens/${mint}/report`, {
    next: { revalidate: 300 },
  });
  if (!res || !res.ok) return null;
  try {
    return (await res.json()) as RugReport;
  } catch {
    return null;
  }
}

type DexPairResp = NonNullable<DexResp["pairs"]>[number];

async function getDex(mint: string): Promise<DexPairResp | null> {
  try {
    const res = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${mint}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as DexResp;
    const sol = (data.pairs ?? []).filter((p) => p.chainId === "solana");
    if (!sol.length) return null;
    return sol.reduce((a, b) => (num(a.volume?.h24) >= num(b.volume?.h24) ? a : b));
  } catch {
    return null;
  }
}

// ── DAS creator lookup ────────────────────────────────────────────────────

interface DasAsset {
  authorities?: { address?: string; scopes?: string[] }[];
  creators?: { address?: string; share?: number }[];
  token_info?: { supply?: number; decimals?: number };
}

function short(a: string): string {
  return a.length > 12 ? `${a.slice(0, 4)}…${a.slice(-4)}` : a;
}

// ── Deep scan: fresh wallets + funding origins ────────────────────────────

interface SigInfo {
  signature: string;
  blockTime?: number | null;
}
interface ParsedTx {
  blockTime?: number;
  transaction?: { message?: { accountKeys?: (string | { pubkey?: string })[] } };
}

async function walletHistory(owner: string): Promise<{ txCount: number; firstSeen: number | null; funder: string | null }> {
  const sigs = await heliusRpc<SigInfo[]>("getSignaturesForAddress", [owner, { limit: 30 }]);
  if (!sigs || !sigs.length) return { txCount: 0, firstSeen: null, funder: null };
  const oldest = sigs[sigs.length - 1];
  const firstSeen = oldest.blockTime ? oldest.blockTime * 1000 : null;

  // Funder heuristic: the first-ever tx's first signer that isn't the owner
  let funder: string | null = null;
  const tx = await heliusRpc<ParsedTx>("getTransaction", [
    oldest.signature,
    { maxSupportedTransactionVersion: 0, encoding: "json" },
  ]);
  const keys = tx?.transaction?.message?.accountKeys ?? [];
  for (const k of keys) {
    const addr = typeof k === "string" ? k : k?.pubkey;
    if (addr && addr !== owner) {
      funder = addr;
      break;
    }
  }
  return { txCount: sigs.length, firstSeen, funder };
}

async function deepScan(
  holders: { owner: string; pct: number }[]
): Promise<{ freshWallets: number; sampled: number; clusters: FundingCluster[]; note: string }> {
  const sample = holders.slice(0, 8); // rate-friendly
  const now = Date.now();
  const FRESH_MS = 7 * 86400 * 1000;
  let fresh = 0;
  const funderMap = new Map<string, { holders: number; pct: number; times: number[] }>();

  for (const h of sample) {
    const hist = await walletHistory(h.owner);
    if (hist.firstSeen && now - hist.firstSeen < FRESH_MS && hist.txCount < 12) fresh++;
    if (hist.funder) {
      const entry = funderMap.get(hist.funder) ?? { holders: 0, pct: 0, times: [] };
      entry.holders += 1;
      entry.pct += h.pct;
      if (hist.firstSeen) entry.times.push(hist.firstSeen);
      funderMap.set(hist.funder, entry);
    }
  }

  const clusters: FundingCluster[] = [];
  funderMap.forEach((v, origin) => {
    if (v.holders < 2) return; // shared funder only matters at 2+
    const span =
      v.times.length >= 2
        ? (Math.max(...v.times) - Math.min(...v.times)) / 3_600_000
        : null;
    clusters.push({
      origin: short(origin),
      holders: v.holders,
      withinHours: span !== null ? Number(span.toFixed(1)) : null,
      pctOfSupply: Number(v.pct.toFixed(1)),
    });
  });
  clusters.sort((a, b) => b.holders - a.holders);

  return {
    freshWallets: fresh,
    sampled: sample.length,
    clusters,
    note: `Sampled the top ${sample.length} non-LP holders (RPC budget). Fresh = wallet <7d old with <12 lifetime txns.`,
  };
}

// ── Birdeye OHLCV for botted-chart detection ──────────────────────────────

async function getOhlcv(mint: string): Promise<OHLCV> {
  try {
    const now = Math.floor(Date.now() / 1000);
    const from = now - 60 * 60 * 24 * 2; // 2 days of 15m candles
    const res = await fetch(
      `https://public-api.birdeye.so/defi/ohlcv?address=${mint}&type=15m&time_from=${from}&time_to=${now}`,
      { headers: { "X-API-KEY": BIRDEYE_KEY, "x-chain": "solana" }, cache: "no-store" }
    );
    if (!res.ok) return [];
    const data = await res.json();
    const items = data?.data?.items ?? [];
    return items.map((c: Record<string, unknown>) => ({
      o: num(c.o), h: num(c.h), l: num(c.l), c: num(c.c), v: num(c.v),
    }));
  } catch {
    return [];
  }
}

// ── DexScreener search for narrative collision ─────────────────────────────

async function searchNarrative(keyword: string): Promise<DexPair[]> {
  try {
    const res = await fetch(
      `https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(keyword)}`,
      { cache: "no-store" }
    );
    if (!res.ok) return [];
    const data = await res.json();
    return (data?.pairs ?? []) as DexPair[];
  } catch {
    return [];
  }
}

// ── Report builder ─────────────────────────────────────────────────────────

function worstOf(checks: SafetyCheck[]): SafetyVerdict {
  if (checks.some((c) => c.verdict === "fail")) return "fail";
  if (checks.some((c) => c.verdict === "warn")) return "warn";
  if (checks.every((c) => c.verdict === "unknown")) return "unknown";
  return "pass";
}

export async function GET(req: NextRequest) {
  const params = new URL(req.url).searchParams;
  const mint = params.get("mint");
  const deep = params.get("deep") === "1";
  if (!mint || !/^[A-Za-z0-9]{30,50}$/.test(mint)) {
    return NextResponse.json({ error: "bad mint" }, { status: 400 });
  }

  // Serve a cached base report (5 min) to survive provider rate limits.
  // Deep scans always run live (they mutate the report with wallet tracing).
  if (!deep) {
    const cached = (await kv(["GET", `mi:safety:${mint}`])) as string | null;
    if (cached) {
      try {
        return NextResponse.json({ ...JSON.parse(cached), cached: true });
      } catch {
        /* fall through to live */
      }
    }
  }

  const [rug, dex, das, ohlcv] = await Promise.all([
    getRugReport(mint),
    getDex(mint),
    heliusRpc<DasAsset>("getAsset", [mint]),
    getOhlcv(mint),
  ]);

  const sources: string[] = [];
  if (rug) sources.push("Rugcheck");
  if (dex) sources.push("DexScreener");
  if (das) sources.push("Helius DAS");

  const checks: SafetyCheck[] = [];
  const symbol = dex?.baseToken?.symbol ?? "?";
  const name = dex?.baseToken?.name ?? "?";

  // Identify the LP / pool addresses to exclude from holder ranking
  const lpAddrs = new Set<string>();
  for (const m of rug?.markets ?? []) {
    if (m.liquidityA) lpAddrs.add(m.liquidityA);
    if (m.liquidityB) lpAddrs.add(m.liquidityB);
  }
  if (dex?.pairAddress) lpAddrs.add(dex.pairAddress);

  // 1. Mint authority
  if (rug || das) {
    const enabled = !!rug?.mintAuthority;
    checks.push({
      id: "mint",
      label: "Mint authority",
      verdict: enabled ? "fail" : "pass",
      value: enabled ? short(rug!.mintAuthority!) : "disabled",
      explain: enabled
        ? "Creator can still print new supply and drain the pool. Hard fail."
        : "Supply is fixed — no one can mint more.",
    });
  }

  // 2. Freeze authority
  if (rug) {
    const enabled = !!rug.freezeAuthority;
    checks.push({
      id: "freeze",
      label: "Freeze authority",
      verdict: enabled ? "fail" : "pass",
      value: enabled ? short(rug.freezeAuthority!) : "disabled",
      explain: enabled
        ? "The honeypot mechanism: your wallet can be frozen so you buy but can't sell. Hard fail."
        : "Your tokens can't be frozen.",
    });
  }

  // 3. LP locked / burned
  const lpPct = Math.max(0, ...(rug?.markets ?? []).map((m) => num(m.lp?.lpLockedPct)));
  if (rug?.markets?.length) {
    checks.push({
      id: "lp",
      label: "LP locked / burned",
      verdict: lpPct >= 90 ? "pass" : lpPct >= 50 ? "warn" : "fail",
      value: `${lpPct.toFixed(0)}% locked`,
      explain:
        lpPct >= 90
          ? "Liquidity is locked/burned — the dev can't pull the rug from under you."
          : lpPct >= 50
            ? "Partially locked — some liquidity can still be pulled."
            : "Liquidity is unlocked — the dev can remove it at any moment. Hard fail.",
    });
  }

  // Full holder table (LP flagged, not removed) — the insider view
  const holders = (rug?.topHolders ?? [])
    .map((h) => {
      const owner = h.owner ?? h.address ?? "";
      const isLp = lpAddrs.has(owner) || lpAddrs.has(h.address ?? "");
      return { owner, pct: num(h.pct), insider: !!h.insider, isLp };
    })
    .filter((h) => h.owner)
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 20);

  // 4. Top holder concentration (LP excluded)
  const nonLp = holders.filter((h) => !h.isLp);
  if (nonLp.length) {
    const top = nonLp[0];
    checks.push({
      id: "concentration",
      label: "Largest non-LP holder",
      verdict: top.pct > 10 ? "fail" : top.pct > 3.5 ? "warn" : "pass",
      value: `${top.pct.toFixed(1)}% (${short(top.owner)})`,
      explain:
        top.pct > 3.5
          ? `One wallet holds ${top.pct.toFixed(1)}% — above the 3.5% line. It can dump on you. (LP pool excluded from ranking.)`
          : "No single trader wallet dominates supply. Distribution looks healthy.",
    });

    // 8. Bundler / insider ratio — majority matters, not a single tag
    const insiders = nonLp.filter((h) => h.insider).length;
    const ratio = nonLp.length ? insiders / nonLp.length : 0;
    checks.push({
      id: "insiders",
      label: "Insider/bundler ratio",
      verdict: ratio > 0.5 ? "fail" : ratio > 0.25 ? "warn" : "pass",
      value: `${insiders}/${nonLp.length} flagged`,
      explain:
        ratio > 0.5
          ? "The majority of top holders are bundler/insider-tagged — supply was split at launch, not organically bought."
          : ratio > 0.25
            ? "Some insider tags present. A few are normal; watch the concentration."
            : "Holder base looks organically distributed.",
    });
  }

  // 5. Volume / Market Cap
  if (dex) {
    const mc = num(dex.marketCap) || num(dex.fdv);
    const vol = num(dex.volume?.h24);
    const ratio = mc > 0 ? vol / mc : 0;
    checks.push({
      id: "volmc",
      label: "Volume / Market Cap (24h)",
      verdict: mc <= 0 ? "unknown" : ratio < 0.8 ? "fail" : ratio < 1.5 ? "warn" : "pass",
      value: mc > 0 ? `${ratio.toFixed(2)}x` : "n/a",
      explain:
        ratio < 0.8
          ? "Volume is below market cap — the price got here without supply changing hands. Wallets are sitting in large unrealized profit, waiting to dump."
          : "Healthy turnover: supply is actively changing hands relative to the cap.",
    });
  }

  // 9. Honeypot triad (up-only + low volume + low holders)
  if (dex && rug) {
    const upOnly = num(dex.priceChange?.h24) >= 0 && num(dex.priceChange?.h6) >= 0 && num(dex.priceChange?.h1) >= 0;
    const lowVol = num(dex.volume?.h24) < 20_000;
    const lowHolders = num(rug.totalHolders) > 0 && num(rug.totalHolders) < 60;
    const triad = upOnly && lowVol && lowHolders;
    checks.push({
      id: "honeypot",
      label: "Honeypot triad",
      verdict: triad ? "fail" : "pass",
      value: `up-only:${upOnly ? "Y" : "N"} lowVol:${lowVol ? "Y" : "N"} fewHolders:${lowHolders ? "Y" : "N"}`,
      explain: triad
        ? "All three lure conditions are true at once: price only goes up, volume is thin, holders are few. Classic honeypot pattern — you may not be able to sell."
        : "Not showing the up-only + low-volume + few-holders lure pattern.",
    });
  }

  // Fees vs MC — honestly unavailable on free tier
  checks.push({
    id: "fees",
    label: "Fees paid vs market cap",
    verdict: "unknown",
    value: "unavailable",
    explain:
      "Accumulated-fee data isn't exposed on the free APIs. Verify on the launchpad directly — a ~15k MC coin should show >0.5 SOL in fees or the cap wasn't built by real trading.",
  });

  // Creator wallet
  const creatorAddr =
    rug?.creator ??
    das?.creators?.[0]?.address ??
    das?.authorities?.find((a) => a.scopes?.includes("full"))?.address ??
    das?.authorities?.[0]?.address ??
    null;
  let creatorStatus: SafetyReport["creator"]["status"] = "unknown";
  let creatorNote = "Creator wallet not resolvable from free sources.";
  if (creatorAddr) {
    const stillTop = nonLp.some((h) => h.owner === creatorAddr);
    creatorStatus = stillTop ? "holding" : "distributing";
    creatorNote = stillTop
      ? "Creator is still among the top holders — has not fully exited."
      : "Creator is not in the visible top holders — may have distributed. Run a deep scan to trace balance changes.";
  }

  // Deep scan (fresh wallets + funding clusters)
  let deepResult: SafetyReport["deep"] = null;
  if (deep && nonLp.length) {
    const d = await deepScan(nonLp.map((h) => ({ owner: h.owner, pct: h.pct })));
    deepResult = {
      ran: true,
      freshWallets: d.freshWallets,
      topSampled: d.sampled,
      fundingClusters: d.clusters,
      note: d.note,
    };
    checks.push({
      id: "fresh",
      label: "Fresh wallets in top holders",
      verdict: d.freshWallets >= 4 ? "fail" : d.freshWallets >= 2 ? "warn" : "pass",
      value: `${d.freshWallets} of top ${d.sampled}`,
      explain:
        d.freshWallets >= 2
          ? "Multiple top holders are brand-new wallets with no history — a strong sign of a coordinated launch, not organic buyers."
          : "Top holders have real wallet history.",
    });
    if (d.clusters.length) {
      const biggest = d.clusters[0];
      checks.push({
        id: "funding",
        label: "Shared funding origin",
        verdict: biggest.holders >= 4 ? "fail" : "warn",
        value: `${biggest.holders} holders from ${biggest.origin}`,
        explain: `${biggest.holders} of the top holders were funded from the same wallet${biggest.withinHours !== null ? ` within ${biggest.withinHours}h of each other` : ""} — that's one entity wearing multiple hats, holding ~${biggest.pctOfSupply}% combined.`,
      });
    }
  }

  // ── Phase-3 detectors ────────────────────────────────────────────────
  // Coin-type classifier (adapts hold-horizon guidance)
  const pairForClass: DexPair = {
    chainId: "solana",
    pairAddress: dex?.pairAddress ?? "",
    baseToken: { address: mint, symbol, name },
    pairCreatedAt: dex?.pairCreatedAt,
  };
  const ct = classifyCoinType(pairForClass);

  // Botted-chart detection
  const botted = detectBottedChart(ohlcv);
  if (botted.length) sources.push("Birdeye OHLCV");
  if (botted[0] && botted[0].confidence >= 0.55) {
    checks.push({
      id: "botted",
      label: "Chart authenticity",
      verdict: botted[0].confidence >= 0.7 ? "fail" : "warn",
      value: `${botted[0].pattern} (${Math.round(botted[0].confidence * 100)}%)`,
      explain: botted[0].explain,
    });
  }

  // Narrative collision + vamp risk
  let collision: SafetyReport["collision"] = null;
  const kw = narrativeKeyword(symbol, name);
  if (kw && kw.length > 2) {
    const searchPairs = await searchNarrative(kw);
    if (searchPairs.length) {
      const c = buildCollision(kw, { symbol, address: mint }, searchPairs);
      collision = {
        keyword: c.keyword,
        competitors: c.competitors.map((x) => ({
          symbol: x.symbol, address: x.address, ageHours: Number(x.ageHours.toFixed(1)),
          fdv: x.fdv, vol24: x.vol24, isLeaderByVol: x.isLeaderByVol, canonicalMatch: x.canonicalMatch,
        })),
        vampRisk: c.vampRisk,
        vampReason: c.vampReason,
      };
      if (c.vampRisk) {
        checks.push({
          id: "vamp",
          label: "Vamp risk",
          verdict: "warn",
          value: `${c.competitors.length} competing tokens`,
          explain: c.vampReason,
        });
      }
    }
  }

  const report: SafetyReport = {
    mint,
    symbol,
    name,
    fetchedAt: Date.now(),
    verdict: worstOf(checks.filter((c) => c.verdict !== "unknown")),
    checks,
    coinType: ct,
    botted: botted.map((b) => ({ pattern: b.pattern, confidence: b.confidence, explain: b.explain })),
    collision,
    holders,
    holderCount: rug?.totalHolders ? num(rug.totalHolders) : null,
    creator: { address: creatorAddr, status: creatorStatus, note: creatorNote },
    deep: deepResult,
    sources,
  };

  if (!sources.length) {
    return NextResponse.json(
      {
        error: "Sources are rate-limited right now — try again in ~30s. (Rugcheck/DexScreener throttle free lookups.)",
        ...report,
      },
      { status: 502 }
    );
  }

  // Cache the base report for 5 minutes to blunt provider rate limits
  if (!deep) {
    await kv(["SET", `mi:safety:${mint}`, JSON.stringify(report), "EX", 300]);
  }
  return NextResponse.json(report);
}
