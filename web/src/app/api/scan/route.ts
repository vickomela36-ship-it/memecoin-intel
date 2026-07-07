import { NextResponse } from "next/server";
import { unstable_cache } from "next/cache";
import { runMemeScan } from "@/modules/memecoin/scanner";

export const dynamic = "force-dynamic";

// One scan every 60s shared by ALL visitors — instead of every browser
// hammering DexScreener with its own full scan.
const getScan = unstable_cache(
  () => runMemeScan({ server: true }),
  ["meme-scan-v1"],
  { revalidate: 60 }
);

export async function GET() {
  try {
    const result = await getScan();
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ error: "scan failed" }, { status: 502 });
  }
}
