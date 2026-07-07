import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const key = process.env.ODDS_API_KEY;
  if (!key) {
    return NextResponse.json(
      { error: "ODDS_API_KEY not configured" },
      { status: 503 }
    );
  }

  const sport = new URL(req.url).searchParams.get("sport") ?? "soccer_epl";
  if (!/^[a-z0-9_]{3,50}$/.test(sport)) {
    return NextResponse.json({ error: "bad sport key" }, { status: 400 });
  }

  const url =
    `https://api.the-odds-api.com/v4/sports/${sport}/odds/` +
    `?regions=uk,eu&markets=h2h&apiKey=${key}`;

  try {
    // 500 req/month free tier — cache aggressively (30 min)
    const res = await fetch(url, { next: { revalidate: 1800 } });
    if (!res.ok) {
      return NextResponse.json(
        { error: `odds api returned ${res.status}` },
        { status: res.status }
      );
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "upstream fetch failed" }, { status: 502 });
  }
}
