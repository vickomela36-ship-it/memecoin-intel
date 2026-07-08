import { NextResponse } from "next/server";
import { cachedScan } from "@/lib/scan-cache";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await cachedScan();
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ error: "scan failed" }, { status: 502 });
  }
}
