import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** Proxy to rugcheck.xyz summary (public API, no key) — avoids CORS issues. */
export async function GET(req: NextRequest) {
  const mint = new URL(req.url).searchParams.get("mint");
  if (!mint || !/^[A-Za-z0-9]{30,50}$/.test(mint)) {
    return NextResponse.json({ error: "bad mint" }, { status: 400 });
  }
  try {
    const res = await fetch(
      `https://api.rugcheck.xyz/v1/tokens/${mint}/report/summary`,
      { next: { revalidate: 600 } }
    );
    if (!res.ok) {
      return NextResponse.json({ error: `rugcheck ${res.status}` }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "rugcheck unreachable" }, { status: 502 });
  }
}
