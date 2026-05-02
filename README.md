memecoin-intel/
├── signals.py        # Buy/sell signal logic (DexScreener API, no auth needed)
├── monitor.py        # Hourly runner: checks signals → email + Notion log
├── config.py         # Env-var loader with validation
├── setup_cron.sh     # One-shot script to register the hourly cron job
├── .env.example      # Template — copy to .env and fill in credentials
└── requirements.txt  # Python dependencies

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in NOTION_API_KEY, GMAIL_USER, GMAIL_APP_PASSWORD
python3 monitor.py     # run once to test
```

## Credentials needed

| Variable | Where to get it |
|---|---|
| `NOTION_API_KEY` | https://www.notion.so/my-integrations → New integration |
| `NOTION_DATABASE_ID` | Pre-filled (`dff606a5-…`) — the existing "Memecoin Buy Now Signals" database |
| `GMAIL_USER` | Your Gmail address used to send alerts |
| `GMAIL_APP_PASSWORD` | https://myaccount.google.com/apppasswords (requires 2FA) |
| `ALERT_EMAIL` | Defaults to `vickomela36@gmail.com` |

## Hourly cron job

```bash
chmod +x setup_cron.sh && ./setup_cron.sh
```

This installs:
```
0 * * * * cd /path/to/memecoin-intel && python3 monitor.py >> cron.log 2>&1
```

Logs are written to `monitor.log` (structured) and `cron.log` (cron stdout/stderr).

## Signal logic (`signals.py`)

Tracks 12 memecoins (PEPE, DOGE, SHIB, BONK, WIF, FLOKI, BRETT, POPCAT, MEW, TURBO, MOODENG, GOAT) on Solana, Ethereum, and Base via the free DexScreener API.

| Signal | Criteria |
|---|---|
| **buy now** | 24h change ≥ 5% AND 1h change ≥ 1% AND volume ≥ $100k AND liquidity ≥ $50k |
| **sell** | 24h change ≤ −10% |
| **hold** | everything else |

## What happens on a "buy now"

1. One HTML email is sent to `ALERT_EMAIL` listing all triggered tokens.
2. Each token gets a row in the **Memecoin Buy Now Signals** Notion database with price, volume, 24h change %, and whether the email was sent.
