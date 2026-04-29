memecoin-intel/
├── scheduler.py      # Hourly runner — entry point
├── signals.py        # Buy/sell signal logic (DexScreener)
├── notifier.py       # Email (Gmail SMTP) + Notion logging
├── config.py         # Loads settings from .env
├── setup_cron.sh     # One-shot cron installer
└── requirements.txt

## Quick start

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
#    Fill in GMAIL_USER, GMAIL_APP_PASSWORD, NOTION_TOKEN

# 3. Share the "Memecoin Buy Signals Log" Notion database with your integration

# 4a. Run continuously (hourly loop)
python scheduler.py

# 4b. OR install as a system cron job (runs once per hour)
bash setup_cron.sh
```

## How it works

Every hour `scheduler.py` calls `signals.py`, which fetches the top 30
boosted tokens on DexScreener for the configured chain and classifies each:

| Signal   | Criteria |
|----------|----------|
| buy now  | 5m change ≥ 3 %, 1h change ≥ 8 %, 5m volume ≥ $5k, liquidity ≥ $30k |
| sell     | 5m change ≤ −5 % |
| hold     | everything else |

For every **buy now** signal:
- An HTML alert email is sent to `vickomela36@gmail.com` via Gmail SMTP
- A row is appended to the **Memecoin Buy Signals Log** Notion database
  (`8ee78806-3289-45b9-8703-8fd78cf405b6`)

## Notion database

Pre-existing database: **Memecoin Buy Signals Log**
Columns: Symbol · Signal · Price USD · Price Change 5m % · Price Change 1h % ·
Volume 5m USD · Liquidity USD · Pair Address · Email Sent · Timestamp

## Gmail setup

1. Enable 2-Step Verification on your Google account
2. Create an App Password: <https://myaccount.google.com/apppasswords>
3. Set `GMAIL_USER` and `GMAIL_APP_PASSWORD` in `.env`
