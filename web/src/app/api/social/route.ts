import { NextRequest, NextResponse } from "next/server";
import { rankPosts, timingContext, type RawPost } from "@/modules/social/analyze";

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

    return NextResponse.json({
      configured: true,
      timing,
      humanCount: human.length,
      botCount: bots.length,
      human: human.slice(0, 12),
    });
  } catch {
    return NextResponse.json({ configured: true, error: "worker unreachable" }, { status: 502 });
  }
}
