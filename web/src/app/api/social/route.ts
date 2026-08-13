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

// X data is NOT available on Vercel serverless — X fights scrapers and
// Agent-Reach needs login cookies + a long-running host. So this route
// proxies to an OPTIONAL self-hosted worker (env XREACH_URL) that runs
// Agent-Reach (`twitter search "<query>"`) and returns normalized posts:
//   [{ author, followers, text, createdAt(ms), url, verified }]
// Without XREACH_URL configured we return configured:false and the UI
// shows a setup state — we never fabricate social data.

interface WorkerPost {
  author?: string;
  handle?: string;
  followers?: number;
  text?: string;
  createdAt?: number | string;
  url?: string;
  verified?: boolean;
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
  const launch = Number(params.get("launch")) || null;
  if (!query) return NextResponse.json({ error: "q required" }, { status: 400 });

  const worker = process.env.XREACH_URL;
  if (!worker) {
    return NextResponse.json({
      configured: false,
      hint: "Set XREACH_URL to a self-hosted Agent-Reach worker to enable social analysis. See web/README for the worker contract.",
    });
  }

  try {
    const res = await fetch(
      `${worker.replace(/\/$/, "")}/search?q=${encodeURIComponent(query)}`,
      {
        headers: process.env.XREACH_TOKEN ? { Authorization: `Bearer ${process.env.XREACH_TOKEN}` } : undefined,
        signal: AbortSignal.timeout(20_000),
        cache: "no-store",
      }
    );
    if (!res.ok) {
      return NextResponse.json({ configured: true, error: `worker ${res.status}` }, { status: 502 });
    }
    const data = await res.json();
    const rawPosts: WorkerPost[] = Array.isArray(data) ? data : data?.posts ?? [];
    const posts = rawPosts.map(normalize).filter((p): p is RawPost => p !== null);

    const { human, bots, earliestHuman } = rankPosts(posts, launch);
    const timing = timingContext(earliestHuman, launch);

    // Coordinated-KOL detection over the human posters.
    const coordinated = detectCoordinatedKOLs(human);

    // If the query is a contract address, this token's human posters become
    // "calls" in the persistent KOL ledger, and each poster's track record +
    // any bio-stated wallet are surfaced. Enrich the token's live mcap first.
    const isCa = /^[A-Za-z0-9]{32,44}$/.test(query);
    let mcap = 0;
    let symbol = "?";
    if (isCa) {
      try {
        const dr = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${query}`, { cache: "no-store" });
        if (dr.ok) {
          const d = await dr.json();
          const sol = (d?.pairs ?? []).filter((p: { chainId?: string }) => p.chainId === "solana");
          const best = sol.sort((a: { volume?: { h24?: number } }, b: { volume?: { h24?: number } }) => (b.volume?.h24 ?? 0) - (a.volume?.h24 ?? 0))[0];
          mcap = Number(best?.marketCap ?? best?.fdv ?? 0);
          symbol = best?.baseToken?.symbol ?? "?";
        }
      } catch { /* mcap stays 0 → ingest is skipped */ }
      await ingestKolPosts(
        query,
        symbol,
        mcap,
        human.map((p) => ({ handle: p.author, hadThesis: p.hasThesis }))
      );
    }

    // Attach each surfaced poster's track record + resolved wallet (best-effort).
    const enrichedHuman = await Promise.all(
      human.slice(0, 12).map(async (p) => ({
        author: p.author,
        followers: p.followers,
        text: p.text,
        createdAt: p.createdAt,
        url: p.url,
        earlyScore: p.earlyScore,
        hasThesis: p.hasThesis,
        wallet: extractWallet(p.text),
        track: isCa ? await kolStats(p.author) : null,
      }))
    );

    return NextResponse.json({
      configured: true,
      timing,
      humanCount: human.length,
      botCount: bots.length,
      coordinated,
      human: enrichedHuman,
    });
  } catch {
    return NextResponse.json({ configured: true, error: "worker unreachable" }, { status: 502 });
  }
}
