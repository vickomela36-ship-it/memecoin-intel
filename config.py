import os

# Buy signal thresholds
BUY_CRITERIA = {
    "min_volume_24h": 500_000,   # $500K 24-hour volume
    "min_price_change_1h": 5.0,  # +5% in the last hour
    "min_liquidity": 50_000,     # $50K liquidity
    "min_txns_1h": 100,          # minimum hourly transactions
}

# Alert recipient
ALERT_EMAIL = "vickomela36@gmail.com"

# Gmail SMTP credentials (set env vars to enable direct sending)
# Generate an App Password at: https://myaccount.google.com/apppasswords
SMTP_USER = os.getenv("GMAIL_USER", "")
SMTP_PASS = os.getenv("GMAIL_APP_PASSWORD", "")

# How long (minutes) before the same coin can trigger another alert
DEDUP_WINDOW_MINUTES = 60

# Local state file for deduplication
STATE_FILE = os.path.join(os.path.dirname(__file__), ".signal_state.json")
