# Memecoin Intel — Web

Terminal-style intelligence dashboard: memecoin scanner, football edge
finder, crypto momentum score — with honest, locally-tracked accuracy.

## Run locally

```bash
cd web
npm install
cp .env.example .env.local   # then fill in your two API keys
npm run dev                  # http://localhost:3000
```

The crypto + memecoin modules work with **no keys at all** (CoinGecko and
DexScreener are public). Football needs both keys in `.env.local`.

## Deploy to Vercel

1. Push this repo to GitHub.
2. In Vercel: **Add New Project** → import the repo.
3. Set **Root Directory** to `web`.
4. Under **Environment Variables**, add:
   - `FOOTBALL_DATA_API_KEY` — from https://www.football-data.org/client/register
   - `ODDS_API_KEY` — from https://the-odds-api.com
5. Deploy. That's it — no database needed.

Keys are server-side only (used inside `/api/football` and `/api/odds`
route handlers). They never appear in the browser bundle. football-data.org
blocks browser CORS anyway, so the proxy is mandatory, and responses are
cached (5 min fixtures / 30 min odds) to stay inside free-tier rate limits.

## Honest-accuracy design

Every surfaced signal is logged to `localStorage` and resolved against
real outcomes:

| Module | Hit definition | Resolution |
|---|---|---|
| Memecoin | Launch +50% / Recovery +20% within 24h | Price refetched from DexScreener |
| Football | Edge pick wins the match | Result fetched from football-data.org |
| Crypto | Direction matches sign of 24h move | Price compared 24h later |

Hit rates only display after 5 resolved signals — before that the UI says
"tracking", never a made-up number. Export the full log as JSON from the
footer.

### Free-tier data honesty

Some inputs from the original spec are not available without paid APIs and
are **not faked**: LP-lock status, holder distribution, funding rates,
social sentiment. Each score's expandable breakdown shows exactly which
components produced the number.

## Structure

```
web/src/
├── app/               # Next.js App Router: page, layout, API proxies
├── components/        # SignalStrip, cards, heatmap, track record, views
├── modules/
│   ├── memecoin/      # DexScreener discovery + launch/recovery scoring
│   ├── football/      # ELO book + edge finder + fetchers
│   └── crypto/        # CoinGecko composite score
├── lib/               # accuracy tracker (localStorage), utils
└── types/             # shared TypeScript interfaces
```

## Optional: social analysis (X/Twitter)

X data can't run on Vercel — X blocks scrapers and Agent-Reach needs login
cookies + a long-running host. The bot-filter and early-poster ranking logic
is built (`src/modules/social/analyze.ts`); it just needs a data source.

To enable: self-host an [Agent-Reach](https://github.com/Panniantong/Agent-Reach)
worker (or any service) exposing:

```
GET {XREACH_URL}/search?q=<query>
→ [{ author, followers, text, createdAt, url, verified }]
```

Then set `XREACH_URL` (and optional `XREACH_TOKEN`) in Vercel env. The SAFETY
tab's Social section then filters bots and surfaces early, credible posters
with timing context (are you early / on time / late). Until configured, the
section shows a setup state — it never fabricates posts.

## Optional: creator ledger + alerts

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `ALERTS_SECRET` — Telegram alerts
  (`/api/alerts`, pinged by an external cron every ~5m)
- Vercel KV (`KV_REST_API_URL` / `KV_REST_API_TOKEN`) — cross-device sync,
  durable alert dedup, and the creator track-record ledger
