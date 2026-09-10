# Memecoin Intel — Setup & Environment

All persistence and external data are driven by environment variables on the
Vercel deployment. The app degrades gracefully: any feature whose key is unset
shows a **dormant** state (never fake data). Check what's live in-app under
**? (help) → STATUS**, or hit `GET /api/status`.

Set these in **Vercel → Project → Settings → Environment Variables**, then
redeploy.

---

## 1. Persistence — Postgres (Neon free tier)  ← you asked to set this up

Powers: the **call ledger** (first-caller attribution), **KOL track-record**,
**creator balance + cluster tracking**, the **trenches heat gauge**, and
**cross-device sync**.

The app uses a tiny key/value layer (`src/lib/kv.ts`) over Postgres via Neon's
serverless driver. Tables are created automatically on first use — no
migration to run. Neon's free tier is generous and permanent.

Steps:

1. Go to **neon.tech** → sign up (free; GitHub login works).
2. **Create a project** (any name), pick a region near your Vercel functions.
3. On the project dashboard, copy the **connection string** (looks like
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`).
   Use the **pooled** connection string if offered.
4. In **Vercel → your project → Settings → Environment Variables**, add:

   ```
   DATABASE_URL = <your Neon connection string>
   ```

   scoped to **Production + Preview**. (The app also accepts `POSTGRES_URL` /
   `POSTGRES_PRISMA_URL` / `POSTGRES_URL_NON_POOLING`, so Neon's official
   **Vercel integration** — which injects those automatically — also works if
   you prefer connecting it that way.)
5. **Redeploy.** Open **? → STATUS**; "Persistence (Postgres)" should read
   **● LIVE**.

Nothing else changes — the ledger routes detect the connection and start
persisting. Without it those routes return empty/dormant and never error.

*Supabase works too:* create a project, copy the **Connection Pooling** string
(port 6543) from Project Settings → Database, and set it as `DATABASE_URL`.

---

## 2. Social signal — LunarCrush  ← your chosen source

Powers: **bot filtering**, **early-poster ranking**, **KOL ledger ingest**,
**coordinated-KOL detection** in the SAFETY tab's Social panel.

1. Create a LunarCrush account and get an API key:
   **lunarcrush.com → Settings → API** (Individual plan has an API allowance;
   check current tiers).
2. Add the env var:

   ```
   LUNARCRUSH_API_KEY=<your key>
   ```
3. Redeploy. In the SAFETY tab, run a token, then click **Social signal** — it
   fetches posts for the token's **symbol/topic** and shows "via LunarCrush".

Notes / honest limits:
- LunarCrush indexes by **symbol/topic**, not contract address. Well-known
  tickers resolve; brand-new or obscure memecoins may return no posts — the
  panel says so rather than inventing data.
- The bot-filter, ranking, KOL ledger, and coordinated-KOL logic all run on
  whatever real posts LunarCrush returns.

*(Alternative, most faithful to raw X: self-host an Agent-Reach worker and set
`XREACH_URL` (+ optional `XREACH_TOKEN`). If both are set, LunarCrush is tried
first, then the worker.)*

---

## 3. Other data sources (already in use)

| Variable | Powers | Notes |
|---|---|---|
| `HELIUS_API_KEY` | Holder tracing, fresh wallets, funding clusters, creator balance, followed-wallet buys | A public fallback key is bundled; set your own for reliability/rate limits. |
| `BIRDEYE_API_KEY` | OHLCV for botted-chart + market-structure TA, whale flow | Set your own to avoid shared-key rate limits. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Outbound scan/HOT alerts | Optional. |
| `CALLS_INGEST_SECRET` | Guards the `POST /api/calls` webhook | Optional; if set, ingest requests must include `"secret": "<value>"`. |
| `PUMPPORTAL_API_KEY` | pump.fun graduation-rate sampling (trenches heat gauge) | Optional. See §5 below. Requires Postgres + the graduation cron. |

---

## 5. Graduation rate — PumpPortal (optional)

Powers the **graduation rate** in the regime/trenches heat gauge — how many
pump.fun tokens are graduating off the bonding curve relative to new launches.

1. Get a PumpPortal data key from **pumpportal.fun**.
2. Add the env var (keep it secret — never commit it):

   ```
   PUMPPORTAL_API_KEY=<your key>
   ```
3. This needs the sampling cron, already declared in `vercel.json`:
   `/api/cron/graduations`, scheduled **daily** (`0 8 * * *`). It connects to
   the PumpPortal WebSocket for ~25s, counts new-token vs migration events, and
   appends a sample to Postgres. The trenches route averages a rolling 24h of
   samples into the rate.

> **Cron frequency & plan — IMPORTANT:** Vercel's **Hobby** plan rejects any
> cron more frequent than **once per day** — a sub-daily schedule (e.g.
> `*/15 * * * *`) makes the whole **deployment fail**. So the schedule is set to
> daily, which yields a coarse single-sample estimate. On **Pro**, bump it to
> `*/15 * * * *` in `vercel.json` for an accurate rolling rate. The metric is
> labelled a sampled estimate either way and doesn't show until the first
> sample lands.

> The graduation rate needs both `PUMPPORTAL_API_KEY` **and** Postgres
> (`DATABASE_URL`) — the cron writes samples there.

---

## 4. Group / webhook call ingest

To auto-log calls from a Telegram group (or Make/Zapier/any webhook), POST to:

```
POST https://<your-deployment>/api/calls
Content-Type: application/json

{ "ca": "<contract address>", "caller": "<handle>", "source": "<group name>",
  "secret": "<CALLS_INGEST_SECRET if you set one>" }
```

The token is auto-enriched with its market cap at call time; the first caller
is attributed once and never overwritten. See the **CALLS** tab.

---

## Verify everything

Open the app → **? (help) → STATUS**. Every row should read **● LIVE** for the
capabilities you configured. Anything still **○ DORMANT** just needs its key.
