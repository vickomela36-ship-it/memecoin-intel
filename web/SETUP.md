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

Steps:

1. In the Vercel dashboard, open your project → **Storage** tab.
2. Click **Create Database → KV** (this is Upstash Redis under the hood).
   Accept the free "Hobby" tier to start.
3. Give it a name (e.g. `memecoin-intel-kv`) and pick the region closest to
   your function region.
4. On the database page, click **Connect Project** and select this project +
   the environments (Production/Preview/Development) you want.
5. Vercel auto-injects the credentials as env vars. Confirm these two exist on
   the project (the app reads exactly these names):

   ```
   KV_REST_API_URL
   KV_REST_API_TOKEN
   ```

   > If you created the store outside Vercel (directly on Upstash), copy the
   > **REST URL** and **REST token** from the Upstash console into those two
   > variable names manually.
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
