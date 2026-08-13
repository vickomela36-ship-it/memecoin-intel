import { NextRequest, NextResponse } from "next/server";
import {
  detectCoordinatedKOLs,
  extractWallet,
  rankPosts,
  timingContext,
  type RawPost,
} from "@/modules/social/analyze";
import { ingestKolPosts, kolStats } from "@/lib/kol";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Social data sources, in priority order:
//   1. LUNARCRUSH_API_KEY — LunarCrush v4 topic posts (works on Vercel, no
//      worker to host). Coverage is by symbol/topic, so best-effort per token.
//   2. XREACH_URL — an optional self-hosted Agent-Reach worker (raw X search).
// If neither is set we return configured:false and the UI shows a setup state.
// We never fabricate social data — only classify/rank what a real source gives.

interface WorkerPost {
  author?: string;
  handle?: string;
  followers?: number;
  text?: string;
  createdAt?: number | string;
  url?: string;
  verified?: boolean;
}

interface LunarPost {
  id?: string | number;
  post_type?: string;
  post_title?: string;
  post_link?: string;
  post_created?: number; // unix seconds
  creator_name?: string;
  creator_display_name?: string;
  creator_followers?: number;
}

const HELIUS_KEY = process.env.HELIUS_API_KEY ?? "8292769f-aeb2-471c-af1d-fb98576972e4";

/** Has this wallet SOLD the given token recently? (Wallets don't lie.) Checks
 *  Helius parsed SWAPs for a transfer of `mint` OUT of the wallet. */
async function walletSoldToken(wallet: string, mint: string): Promise<boolean> {
  try {
    const res = await fetch(
      `https://api.helius.xyz/v0/addresses/${wallet}/transactions?api-key=${HELIUS_KEY}&type=SWAP&limit=15`,
      { cache: "no-store", signal: AbortSignal.timeout(8000) }
    );
    if (!res.ok) return false;
    const txs = (await res.json()) as { tokenTransfers?: { fromUserAccount?: string; mint?: string }[] }[];
    return (txs ?? []).some((tx) =>
      (tx.tokenTransfers ?? []).some((t) => t.fromUserAccount === wallet && t.mint === mint)
    );
  } catch {
    return false;
  }
}

/** Fetch + normalize LunarCrush topic posts for a symbol/topic. */
async function fetchLunar(topic: string, apiKey: string): Promise<RawPost[] | null> {
  try {
    const t = topic.toLowerCase().replace(/^\$/, "").replace(/[^a-z0-9]/g, "");
    if (!t) return null;
    const res = await fetch(`https://lunarcrush.com/api4/public/topic/${t}/posts/v1`, {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(15_000),
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    const rows: LunarPost[] = data?.data ?? [];
    return rows
      .map((p): RawPost | null => {
        const author = p.creator_name ?? p.creator_display_name ?? "";
        const text = p.post_title ?? "";
        if (!author || !text) return null;
        return {
          author: author.replace(/^@/, ""),
          followers: Number(p.creator_followers) || 0,
          text,
          createdAt: p.post_created ? p.post_created * 1000 : Date.now(),
          url: p.post_link,
          verified: false,
        };
      })
      .filter((p): p is RawPost => p !== null);
  } catch {
    return null;
  }
}

function normalize(p: WorkerPost): RawPost | null {
  const author = p.author ?? p.handle ?? "";
  const text = p.text ?? "";
  if (!author || !text) return null;
  const createdAt =
    typeof p.createdAt === "number"
      ? p.createdAt
      : p.createdAt
        ? Date.parse(p.createdAt)
        : Date.now();
  return {
    author,
    followers: Number(p.followers) || 0,
    text,
    createdAt: isFinite(createdAt) ? createdAt : Date.now(),
    url: p.url,
    verified: !!p.verified,
  };
}

export async function GET(req: NextRequest) {
  const params = new URL(req.url).searchParams;
  const query = params.get("q");
  const symbol = params.get("symbol");
  const launch = Number(params.get("launch")) || null;
  if (!query) return NextResponse.json({ error: "q required" }, { status: 400 });

  const lunarKey = process.env.LUNARCRUSH_API_KEY;
  const worker = process.env.XREACH_URL;
  if (!lunarKey && !worker) {
    return NextResponse.json({
      configured: false,
      hint: "Set LUNARCRUSH_API_KEY (recommended — works on Vercel) or XREACH_URL (self-hosted worker) to enable social analysis. See SETUP.md.",
    });
  }

  try {
    let posts: RawPost[] = [];
    let source = "";

    // 1. LunarCrush by symbol/topic (falls back to the query if no symbol).
    if (lunarKey) {
      const topic = symbol || query;
      const lunar = await fetchLunar(topic, lunarKey);
      if (lunar && lunar.length) {
        posts = lunar;
        source = "LunarCrush";
      }
    }
    // 2. XREACH worker (raw X search) — used if configured and LunarCrush was
    //    empty or unavailable.
    if (!posts.length && worker) {
      const res = await fetch(
        `${worker.replace(/\/$/, "")}/search?q=${encodeURIComponent(query)}`,
        {
          headers: process.env.XREACH_TOKEN ? { Authorization: `Bearer ${process.env.XREACH_TOKEN}` } : undefined,
          signal: AbortSignal.timeout(20_000),
          cache: "no-store",
        }
      );
      if (res.ok) {
        const data = await res.json();
        const rawPosts: WorkerPost[] = Array.isArray(data) ? data : data?.posts ?? [];
        posts = rawPosts.map(normalize).filter((p): p is RawPost => p !== null);
        source = "Agent-Reach";
      }
    }

    if (!posts.length) {
      return NextResponse.json({
        configured: true,
        source: source || (lunarKey ? "LunarCrush" : "Agent-Reach"),
        timing: { label: "UNKNOWN", detail: "No posts found for this token from the connected source (coverage is by symbol; new/obscure tokens may be missing)." },
        humanCount: 0,
        botCount: 0,
        human: [],
      });
    }

    const { human, bots, earliestHuman } = rankPosts(posts, launch);
    const timing = timingContext(earliestHuman, launch);

    // Coordinated-KOL detection over the human posters.
    const coordinated = detectCoordinatedKOLs(human);

    // If the query is a contract address, this token's human posters become
    // "calls" in the persistent KOL ledger, and each poster's track record +
    // any bio-stated wallet are surfaced. Enrich the token's live mcap first.
    const isCa = /^[A-Za-z0-9]{32,44}$/.test(query);
    let mcap = 0;
    let caSymbol = symbol ?? "?";
    if (isCa) {
      try {
        const dr = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${query}`, { cache: "no-store" });
        if (dr.ok) {
          const d = await dr.json();
          const sol = (d?.pairs ?? []).filter((p: { chainId?: string }) => p.chainId === "solana");
          const best = sol.sort((a: { volume?: { h24?: number } }, b: { volume?: { h24?: number } }) => (b.volume?.h24 ?? 0) - (a.volume?.h24 ?? 0))[0];
          mcap = Number(best?.marketCap ?? best?.fdv ?? 0);
          caSymbol = best?.baseToken?.symbol ?? caSymbol;
        }
      } catch { /* mcap stays 0 → ingest is skipped */ }
      await ingestKolPosts(
        query,
        caSymbol,
        mcap,
        human.map((p) => ({ handle: p.author, hadThesis: p.hasThesis }))
      );
    }

    // Attach each surfaced poster's track record + resolved wallet, and — if
    // they pasted a wallet and this is a CA — cross-check whether that wallet
    // is SELLING the very token they're posting about. Wallets don't lie.
    const enrichedHuman = await Promise.all(
      human.slice(0, 12).map(async (p) => {
        const wallet = extractWallet(p.text);
        const sellingWhatTheyShill = wallet && isCa ? await walletSoldToken(wallet, query) : false;
        return {
          author: p.author,
          followers: p.followers,
          text: p.text,
          createdAt: p.createdAt,
          url: p.url,
          earlyScore: p.earlyScore,
          hasThesis: p.hasThesis,
          wallet,
          sellingWhatTheyShill,
          track: isCa ? await kolStats(p.author) : null,
        };
      })
    );

    return NextResponse.json({
      configured: true,
      source,
      timing,
      humanCount: human.length,
      botCount: bots.length,
      coordinated,
      human: enrichedHuman,
    });
  } catch {
    return NextResponse.json({ configured: true, error: "social source unreachable" }, { status: 502 });
  }
}
