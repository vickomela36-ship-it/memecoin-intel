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

## Slice 1 — one scan pipeline (pending)
## Slice 2 — data-layer hygiene (pending)
## Slice 3 — code-split + progressive paint (pending)
