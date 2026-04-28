memecoin-intel/
├── signals.py        # Buy/sell signal logic (DexScreener API, no key needed)
├── check_signals.py  # Orchestrator — outputs JSON with buy_now list
├── notify.py         # Standalone email + Notion notifier (needs env vars)
├── config.py         # Thresholds, email, Notion DB id, watched pairs
└── requirements.txt

## How signals work

`signals.py` fetches the top meme pairs from DexScreener and classifies each as:
- **buy now** — 1h change ≥ 3%, 24h volume ≥ $50k, buy pressure ≥ 55%
- **sell** — 1h change ≤ -5% OR buy pressure ≤ 40%
- **hold** — everything else

Thresholds live in `config.py`.

## Hourly alerting (two modes)

### Mode 1 — Claude Code session (no credentials needed)

The Claude Code session runs a persistent monitor that fires every hour.
On each tick Claude:
1. Runs `python check_signals.py`
2. Sends a Gmail alert via the Gmail MCP tool for every `buy now` token
3. Logs a row in the "Memecoin Buy Signals" Notion database

This mode is active whenever this Claude Code session is open.

### Mode 2 — standalone cron (survives session restarts)

Set the following env vars (e.g. in `~/.env` sourced by cron):

```
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # Gmail App Password
NOTION_API_KEY=secret_...                 # Notion integration token
```

Then install the cron entry:

```bash
0 * * * * cd /home/user/memecoin-intel && python check_signals.py | python notify.py >> /var/log/memecoin-intel.log 2>&1
```

## Notion database

Existing DB: **Memecoin Buy Signals**  
Data source ID: `684a50fb-f6b5-44c6-b1f5-36a3a6f2679e`

Columns: Token · Symbol · Signal · Price USD · 1h/6h/24h Change % · Volume 24h · Liquidity · Buy Pressure · DexScreener URL · Checked At

## Watching specific pairs

Add pair addresses to `WATCHED_PAIRS` in `config.py`:

```python
WATCHED_PAIRS = [
    "solana/7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",   # Wrapped SOL
    "bsc/0x...",
]
```

When the list is non-empty, only those pairs are checked instead of trending tokens.
