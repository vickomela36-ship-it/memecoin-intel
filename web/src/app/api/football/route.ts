import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BASE = "https://api.football-data.org/v4";

export async function GET(req: NextRequest) {
  const key = process.env.FOOTBALL_DATA_API_KEY;
  if (!key) {
    return NextResponse.json(
      { error: "FOOTBALL_DATA_API_KEY not configured" },
      { status: 503 }
    );
  }

  const { searchParams } = new URL(req.url);
  const matchId = searchParams.get("match");
  const comp = searchParams.get("comp");
  const status = searchParams.get("status") ?? "SCHEDULED";

  let url: string;
  if (matchId) {
    if (!/^\d+$/.test(matchId)) {
      return NextResponse.json({ error: "bad match id" }, { status: 400 });
    }
    url = `${BASE}/matches/${matchId}`;
  } else if (comp) {
    if (!/^[A-Z0-9]{2,5}$/.test(comp)) {
      return NextResponse.json({ error: "bad competition code" }, { status: 400 });
    }
    url = `${BASE}/competitions/${comp}/matches?status=${encodeURIComponent(status)}`;
  } else {
    return NextResponse.json({ error: "comp or match required" }, { status: 400 });
  }

  try {
    const res = await fetch(url, {
      headers: { "X-Auth-Token": key },
      // football-data free tier: 10 req/min — cache identical calls for 5 min
      next: { revalidate: 300 },
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `football-data.org returned ${res.status}` },
        { status: res.status }
      );
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "upstream fetch failed" }, { status: 502 });
  }
}
