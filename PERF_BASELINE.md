# PERF_BASELINE.md — Memecoin Intel v2 (pre-optimization)

Captured from static analysis of the codebase at the start of the v2 efficiency
pass. Runtime browser metrics (Lighthouse, LCP) require the live URL and are
listed with capture method rather than fabricated.

## Codebase map

- **Framework:** Next.js 14 App Router, single client page (`app/page.tsx`) that
  mounts all views; deployed on Vercel.
- **State:** browser `localStorage` + Vercel KV sync (`lib/sync.ts`). No DB tables.
- **Data layer:** SWR in 12 call sites, **no global `SWRConfig`** (no shared
  `dedupingInterval`/`staleTime`). ~10,700 LOC across `src`.
- **11 API routes:** alerts, creators, football, lp, odds, rugcheck, safety,
  scan, social, sync, whales.

## Provider inventory + current caching

| Provider | Key? | Reached from | Cache today |
|---|---|---|---|
| DexScreener | no | **client** (`fetchPairsBatch`, `fetchTokenPrice`) + `/api/scan` | scan: `unstable_cache` 60s; client calls: **none** |
| Binance FAPI | no | **client** (`buildAllTickets` in CryptoView) | **none** |
| Bybit | no | **client** (perps fallback) | **none** |
| CoinGecko | no | **client** (`fetchMajorsUp` in RegimeBanner) | **none** |
| Rugcheck | no | `/api/safety`, `/api/rugcheck`, `/api/creators` | 300–600s route cache + KV 300s |
| Helius RPC | yes (env) | `/api/safety`, `/api/whales` | whale: `unstable_cache` 300s |
| Birdeye | yes (env) | `/api/safety`, `/api/whales` | route cache |
| Football-Data | yes (env) | `/api/football` | 300s |
| Odds API | yes (env) | `/api/odds` | 1800s |
| Meteora DLMM | no | `/api/lp` | `unstable_cache` 300s |

## Key-leak audit — PASS

No provider **key** reaches the client bundle: every keyed provider (Helius,
Birdeye, Football-Data, Odds) is behind an `/api/*` route. ✅ Guardrail met.

**But** three keyless providers are hit **directly from the browser**, which is
the efficiency problem (N calls per visitor, no shared cache, no coalescing):
- `CryptoView` → `buildAllTickets` → Binance FAPI
- `RegimeBanner` → CoinGecko
- `PortfolioView`, `PositionsView`, `WatchSafetyPopup` → DexScreener `fetchPairsBatch`

## Measured request fan-out (the redundant work)

- **Perps tab (CryptoView):** `buildPerpTicket` issues **7 Binance calls per
  symbol** (premium, ticker, 1h klines, 4h klines, OI hist, L/S ratio, taker) +
  1 aggTrades whale call = **8 × 6 symbols = ~48 client-side calls per load**,
  uncached, repeated every 30s refresh and on every device. This is the single
  biggest efficiency hole.
- **Memecoins + Confluence** both call `/api/scan` independently → 2 hits, but
  server-cached 60s so cheap. Still a client-side duplicate to coalesce.
- **RegimeBanner** (mounted on Memecoins) → 1 CoinGecko call per load, uncached.
- **Portfolio / Positions / WatchSafetyPopup** → `fetchPairsBatch` (1 DexScreener
  call per, up to 30 addrs), polled every 60s, uncached across components.

## Bundle / code-splitting

- **No code-splitting by surface** — no `next/dynamic`/`lazy` anywhere. All 10
  views (memecoin, confluence, safety, creators, positions, challenge,
  portfolio, perps, football, lp) + Recharts ship in the initial JS.
- Largest chunks today: `fd9d1056` 173 KB, `framework` 140 KB, `117-*` 124 KB,
  `main` 117 KB, `polyfills` 113 KB. Opening Memecoins ships the football, perp,
  and LP code too.

## First-paint behavior (observed in code)

`page.tsx` mounts the memecoin, football, and crypto views simultaneously
(`display:none` toggling), so all three data hooks fire on load → multiple
concurrent "loading…" blocks, exactly the reported symptom. There is no
per-panel streaming; each view shows its own spinner until its hook resolves.

## Runtime metrics — TO CAPTURE on live URL (method, not fabricated)

Run against `https://memecoin-intel-baoa.vercel.app` and fill in:
- **Lighthouse mobile + desktop:** `npx lighthouse <url> --preset=desktop` and
  mobile default → record Performance, LCP, TBT, CLS.
- **Per-surface TTFMP:** DevTools Performance trace, one per tab.
- **Network waterfall:** DevTools Network, hard reload per surface → total
  requests, blocking requests, payload sizes.
These are the before-numbers Pillar A's `PERF_RESULTS.md` must beat.

## Biggest wins ranked (static analysis)

1. **Server-aggregate the perp desk** (`/api/perps`, EU region, cached 15–30s):
   ~48 client calls → **1** per load. Largest single win.
2. **Server-aggregate + cache CoinGecko majors** (fold into regime route).
3. **Global SWR config** (`dedupingInterval`, `staleTime`) — kills refetch churn.
4. **Code-split views** with `next/dynamic` — Memecoins stops shipping football/perp/LP JS.
5. **Coalesce DexScreener price fetches** behind one `/api/prices?addrs=` route
   shared by Portfolio/Positions/WatchPopup.
