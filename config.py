import os

# ─── Signal Thresholds ────────────────────────────────────────────────────────
DUMP_THRESHOLD_H6     = -20.0    # h6 price drop % to classify as a dump
RECOVERY_H1_MIN       = 3.0      # h1 recovery % needed to trigger BUY NOW
MIN_LIQUIDITY_USD     = 50_000   # minimum pool liquidity ($)
MIN_VOLUME_H24_USD    = 200_000  # minimum 24h trading volume ($)
MIN_FDV_USD           = 500_000  # minimum fully-diluted valuation ($)
MAX_FDV_USD           = 100_000_000  # ignore large-cap tokens
MIN_BUY_RATIO         = 0.55     # buy txns / total txns in h1
NOTIFY_COOLDOWN_HOURS = 4        # hours before re-alerting the same token

# ─── Notification ─────────────────────────────────────────────────────────────
ALERT_EMAIL  = "vickomela36@gmail.com"
NOTION_DB_ID = "fdab4e7b-859d-4a83-8db8-743fcad7cbe4"

# ─── Credentials (set via .env or environment variables) ──────────────────────
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTION_API_KEY     = os.getenv("NOTION_API_KEY", "")
