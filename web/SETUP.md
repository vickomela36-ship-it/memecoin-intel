# Memecoin Intel — Setup & Environment

All persistence and external data are driven by environment variables on the
Vercel deployment. The app degrades gracefully: any feature whose key is unset
shows a **dormant** state (never fake data). Check what's live in-app under
**? (help) → STATUS**, or hit `GET /api/status`.

Set these in **Vercel → Project → Settings → Environment Variables**, then
redeploy.

---

## 1. Persistence — Vercel KV (Upstash Redis)  ← you asked to set this up

Powers: the **call ledger** (first-caller attribution), **KOL track-record**,
**creator balance + cluster tracking**, the **trenches heat gauge**, and
**cross-device sync**.

Vercel no longer has a built-in "KV" — it's now provided through the
**Upstash** marketplace entry (serverless Redis with a REST API, which is what
this app talks to).

Steps:

1. In the Vercel dashboard, open your project → **Storage → Create Database**.
2. Under **Marketplace Database Providers**, pick **Upstash**
   (*Serverless DB — Redis, Vector, Queue, Search*).
   - **Do NOT** pick "Redis — Official Redis for Vercel"; that's a raw
     `redis://` connection, not the REST API this app uses.
3. Choose **Redis**, the free tier, and a region near your function region.
4. **Connect** it to this project and select the environments
   (Production/Preview/Development) you want.
5. Vercel/Upstash auto-injects the REST credentials. The app accepts **either**
   naming, so whichever pair it creates will work:

   ```
   KV_REST_API_URL          / KV_REST_API_TOKEN
     — or —
   UPSTASH_REDIS_REST_URL   / UPSTASH_REDIS_REST_TOKEN
   ```

   You don't need to rename anything.
6. **Redeploy.** Open **? → STATUS**; "Persistence (Vercel KV)" should read
   **● LIVE**.

Nothing else changes — the ledger routes detect the vars and start persisting.
Without them those routes return empty/dormant and never error.

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
