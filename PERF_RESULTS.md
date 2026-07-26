# PERF_RESULTS.md — measured before/after per slice

Each number is re-measured against `PERF_BASELINE.md`. Runtime Lighthouse/LCP
are captured on the live URL after each deploy (method in the baseline).

## Slice 0 — Strip to memecoin-only

**What changed:** deleted the Football, Perp desk, and LP surfaces (views,
routes, modules, deps) and the CoinGecko regime call. Restore point:
`full-platform-v1` tag + `origin/main` @ commit before the strip.

| Metric | Before | After | Δ |
|---|---|---|---|
| API routes | 11 | **8** | −3 (football, odds, lp) |
| Client-side external calls / load (perp desk open) | **~48** (Binance ×8/symbol ×6) | **0** | −48 |
| Client-side external calls / load (CoinGecko regime) | 1 | **0** | −1 |
| Main page route size | — | 36.7 kB | (perps/football/lp no longer in initial JS) |
| First Load JS (shared) | 87.4 kB | **87.2 kB** | baseline; big drop comes in Slice 3 (code-split) |
| npm dependencies | +recharts (37 transitive) | **recharts removed** | −37 packages |
| Surfaces / views | 10 | **7** (Scanner, Confluence, Creators, Safety, Positions, Portfolio, Challenge) | −3 |

**Biggest win:** removing the perp desk eliminated ~48 uncached client-side
Binance calls per visitor per load — the single largest source of redundant
network work identified in the baseline — at zero cost, because it was a
deleted surface.

**Runtime (capture on live URL):** re-run Lighthouse mobile/desktop and the
Memecoins-tab network waterfall; expect fewer blocking requests now that
football + perp hooks no longer fire on load.

---

## Slice 1+2 — kill redundant client work

**What changed:** global `SWRConfig` (dedupe + keep-previous-data) and a
shared, edge-cached `/api/prices` route replacing direct client DexScreener
calls in Portfolio + Positions + entry-check.

| Metric | Before | After | Δ |
|---|---|---|---|
| `/api/scan` fetches when Scanner + Confluence both open | 2 independent | **1** (coalesced by `dedupingInterval` 20s) | −1, and no thundering herd |
| DexScreener calls from price polling | Portfolio + Positions each hit DexScreener directly every 60s, uncached, per device | **1 shared `/api/prices`** edge-cached 25s — DexScreener hit once/25s total regardless of components or devices | large cut under multi-device / multi-panel use |
| Client refetch on tab focus | every focus | throttled 30s | fewer wasted calls |
| Blank panels on revalidate | yes (data cleared) | **no** (`keepPreviousData`) | UX + fewer perceived reloads |
| Provider keys in client | 0 (already) | 0 | maintained |

`/api/prices` sets `Cache-Control: s-maxage=25, stale-while-revalidate=60`
so Vercel's edge serves most requests without touching the function, and a
throttled provider serves last-good rather than blanking.

## Slice 3 — code-split + progressive paint

**What changed:** every non-default view (`Confluence`, `Safety`, `Creators`,
`Positions`, `Portfolio`, `Challenge`, `Education`, `WatchSafetyPopup`) is now
`next/dynamic` lazy-loaded with a panel skeleton — only the Scanner loads on
first paint; the rest fetch their JS when their tab is first opened.

| Metric | Before (post-strip) | After code-split | Δ |
|---|---|---|---|
| Main route (`/`) JS | 36.7 kB | **15.7 kB** | **−57%** |
| First Load JS | 124 kB | **108 kB** | −16 kB |
| Views shipped on first paint | 7 | **1** (Scanner) + skeletons | −6 |

Opening the Scanner no longer downloads the Positions/Portfolio/Challenge/
Safety/Creators/Confluence code. Combined with the Slice-0 strip (which
removed the football/perp/LP/Recharts weight entirely), first-paint JS is a
fraction of the pre-v2 bundle.

## Slice 4 — unified sentiment engine (pending)
## Slice 5 — signal efficiency / per-type hit-rate (pending)
## Slice 6 — UI pass (design plan first) (pending)
## Slice 4 — unified sentiment engine (pending)
## Slice 5 — signal efficiency / per-type hit-rate (pending)
## Slice 6 — UI pass (design plan first) (pending)
