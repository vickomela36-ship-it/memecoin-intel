## memecoin-intel

Hourly Solana memecoin signal monitor. Sends a Gmail alert and logs every **buy now** signal to Notion.

```
memecoin-intel/
├── signals.py       # DexScreener signal detection
├── notifier.py      # Gmail (SMTP) + Notion API
├── run_check.py     # Hourly entrypoint (run via cron)
├── config.py        # API keys & settings  ← fill this in
├── setup_cron.sh    # Installs the cron job
├── requirements.txt
├── tracker.py       # PnL logging (coming soon)
├── meteora.py       # LP position monitor (coming soon)
└── dashboard.py     # Streamlit UI (coming soon)
```

### Signal criteria

A token triggers **buy now** when all four conditions hold:

| Metric | Threshold |
|---|---|
| 24h price change | > 15% |
| 24h volume | > $500k |
| Liquidity | > $100k |
| Buy txns vs sell txns (1h) | buys > sells |

---

### Setup

#### 1. Install dependencies

```bash
pip install -r requirements.txt
```

#### 2. Configure `config.py`

**Gmail App Password**
1. Enable 2-Step Verification on your Google account.
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Create an app called *Memecoin Intel* and copy the 16-char password.
4. Set `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, and `ALERT_EMAIL` in `config.py`.

**Notion integration token**
1. Go to [notion.so/my-integrations](https://notion.so/my-integrations) → **New integration**.
2. Copy the `ntn_…` token into `NOTION_TOKEN`.
3. Open the **Memecoin Buy Signals** database in Notion.
4. Click **···** → **Add connections** → select your integration.

The Notion database was pre-created at:
`https://www.notion.so/347d49061af04a12b116e0601217bcaf`

#### 3. Test manually

```bash
python run_check.py
```

#### 4. Schedule hourly via cron

```bash
chmod +x setup_cron.sh
./setup_cron.sh                            # system python3
# OR with a virtualenv:
./setup_cron.sh /path/to/venv/bin/python
```

This installs: `0 * * * * python run_check.py >> memecoin.log 2>&1`

Logs are written to `memecoin.log` in the project directory.
