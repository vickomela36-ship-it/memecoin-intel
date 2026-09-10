import { NextResponse } from "next/server";
import { cachedScan } from "@/lib/scan-cache";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await cachedScan();
    // The scan data refreshes every 60s (cachedScan). Let Vercel's edge serve
    // that same window so repeat loads/refreshes don't each invoke the function.
    return NextResponse.json(result, {
      headers: { "Cache-Control": "s-maxage=60, stale-while-revalidate=120" },
    });
  } catch {
    return NextResponse.json({ error: "scan failed" }, { status: 502 });
  }
}
