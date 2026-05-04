# memecoin-intel

Hourly memecoin buy-signal monitor. Sends an email alert and logs to Notion
every time a token meets the **buy now** criteria.

```
memecoin-intel/
├── signals.py        # Buy/sell signal logic (DexScreener API)
├── monitor.py        # Hourly runner — email + Notion logging
├── config.py         # Thresholds and credentials (reads .env)
├── requirements.txt
├── .env.example      # Credential template
└── setup_cron.sh     # One-shot cron installer
```

## Quick start

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Set credentials
cp .env.example .env
# Edit .env — add NOTION_TOKEN, GMAIL_SENDER, GMAIL_APP_PASSWORD

# 3. Test a single run
python3 monitor.py

# 4. Install hourly cron
bash setup_cron.sh
```

## Signal criteria (edit config.py to tune)

| Metric | Threshold |
|---|---|
| 1-hour price change | ≥ +5% |
| 24-hour volume | ≥ $50,000 |
| Liquidity | ≥ $10,000 |
| Volume / Liquidity ratio | ≥ 0.30 |

All four must pass for a **buy now** signal.

## Credentials

| Variable | Where to get it |
|---|---|
| `NOTION_TOKEN` | [notion.so/my-integrations](https://www.notion.so/my-integrations) — create an integration and share the DB with it |
| `GMAIL_SENDER` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification) |

## Notion database

Signals are logged to the **Memecoin Buy Now Signals** database  
(`ec3ba050-a06d-40c2-a92e-a87b51ceb459`) with columns:
Token, Chain, Token Address, Price USD, Price Change 1h %, Volume 24h,
Liquidity USD, DexScreener URL, Signal, Logged At.

## Token watch list

By default the monitor watches DexScreener's trending/boosted tokens.  
To watch specific tokens, set `WATCH_LIST` in `.env`:

```
WATCH_LIST=So11111111111111111111111111111111111111112,0xabc...
```
