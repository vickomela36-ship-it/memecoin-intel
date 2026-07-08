import { unstable_cache } from "next/cache";
import { runMemeScan } from "@/modules/memecoin/scanner";

// One scan every 60s shared by ALL consumers (the /api/scan route for the
// dashboard AND the /api/alerts watcher) — single source of truth.
export const cachedScan = unstable_cache(
  () => runMemeScan({ server: true }),
  ["meme-scan-v1"],
  { revalidate: 60 }
);
