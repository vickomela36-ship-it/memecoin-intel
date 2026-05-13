memecoin-intel/
├── run_daily.py      # Entry point — run this daily via cron
├── signals.py        # Buy/sell signal logic (DexScreener)
├── notifier.py       # Gmail email + Notion logging
├── config.py         # Loads env vars and thresholds
├── tracker.py        # PnL logging
├── meteora.py        # LP position monitor
├── dashboard.py      # Streamlit UI
└── requirements.txt

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in .env with your credentials
```

### Gmail
1. Enable 2FA on your Google account.
2. Go to https://myaccount.google.com/apppasswords and create an App Password.
3. Set `GMAIL_SENDER` and `GMAIL_APP_PASSWORD` in `.env`.

### Notion
1. Go to https://www.notion.so/my-integrations and create an integration.
2. Copy the **Internal Integration Token** into `NOTION_TOKEN` in `.env`.
3. Open the **Memecoin Buy Signals** database in Notion → ··· → **Add connections** → select your integration.

## Run manually

```bash
python run_daily.py
```

## Schedule daily (cron)

Run at 09:00 every morning:

```
0 9 * * * cd /path/to/memecoin-intel && /usr/bin/python3 run_daily.py
```

Edit with:
```bash
crontab -e
```

Logs are written to `memecoin_intel.log` in the project directory.

## How it works

1. **signals.py** fetches live pair data from the DexScreener API (no key needed)  
   and applies four filters to every pair across Solana, Ethereum, and BSC:
   - Liquidity ≥ $50k
   - 24h volume ≥ $100k
   - Vol/Liq ratio ≥ 1.5 (momentum)
   - 24h price change ≥ +5%

2. When any pair passes all filters its signal is **"buy now"**.

3. **notifier.py** sends one HTML email to `vickomela36@gmail.com` listing all  
   buy-now signals, then logs each signal as a row in the  
   **Memecoin Buy Signals** Notion database with an `Email Sent` checkbox.
