# memecoin-intel

Daily memecoin signal scanner — fetches trending Solana tokens from DexScreener,
generates **buy now / hold / sell** signals, and on every "buy now":

- Sends an HTML email to `vickomela36@gmail.com`
- Logs the signal to the **Memecoin Buy Now Signals** Notion database

## Files

```
memecoin-intel/
├── signals.py        # Buy/sell signal logic (DexScreener)
├── daily_runner.py   # Orchestrator: email + Notion on buy now
├── tracker.py        # PnL trade logging
├── meteora.py        # Meteora DLMM LP position monitor
├── dashboard.py      # Streamlit UI
├── config.py         # Env-driven configuration
└── requirements.txt
```

## GitHub Actions (daily cron)

The workflow `.github/workflows/daily.yml` runs at **09:00 UTC every day**.

Add these secrets to your repo (`Settings → Secrets → Actions`):

| Secret | Description |
|---|---|
| `GMAIL_USER` | Gmail address used to send alerts |
| `GMAIL_APP_PASSWORD` | [Gmail App Password](https://myaccount.google.com/apppasswords) (not your login password) |
| `NOTION_TOKEN` | Notion integration secret (`ntn_…`) |
| `NOTION_DATABASE_ID` | Leave blank to use the existing DB (`958c4eaa-…`) |
| `SOLANA_WALLET_ADDRESS` | *(optional)* Your wallet for Meteora LP tracking |

## Local run

```bash
pip install -r requirements.txt
export GMAIL_USER=you@gmail.com
export GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
export NOTION_TOKEN=ntn_...
python daily_runner.py
```

## Streamlit dashboard

```bash
streamlit run dashboard.py
```

## Signal logic

A coin is marked **buy now** when:
- 24 h price change ≥ 15 %
- 24 h volume ≥ $100 k

Confidence score (0–100 %) weights price momentum, volume, and liquidity.
