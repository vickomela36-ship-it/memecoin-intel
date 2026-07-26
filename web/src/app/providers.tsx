"use client";

import { SWRConfig } from "swr";
import { jsonFetcher } from "@/lib/utils";

/**
 * Global data-layer config. The key efficiency lever: dedupingInterval
 * coalesces identical in-flight requests — Scanner and Confluence both
 * pull /api/scan, and this makes that ONE request, not two. Per-request
 * staleTime is set at each useSWR call site via refreshInterval.
 */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher: (url: string) => jsonFetcher(url),
        dedupingInterval: 20_000, // coalesce identical fetches within 20s
        focusThrottleInterval: 30_000, // don't refetch on every tab focus
        keepPreviousData: true, // show last-good while revalidating (no blank)
        revalidateOnReconnect: true,
        errorRetryCount: 3,
      }}
    >
      {children}
    </SWRConfig>
  );
}
