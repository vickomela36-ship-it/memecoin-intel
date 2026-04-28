# ── Tokens to monitor ────────────────────────────────────────────────────────
# Add every pair you want tracked.
# 'address' is the DexScreener pair address (chain prefix optional).
# Example: {'name': 'BONK', 'address': 'solana/YOUR_PAIR_ADDRESS'}
TOKENS_TO_WATCH = [
    # {'name': 'TOKEN_NAME', 'address': 'DEXSCREENER_PAIR_ADDRESS'},
]

# ── Email (Gmail SMTP) ────────────────────────────────────────────────────────
# Create an App Password at: https://myaccount.google.com/apppasswords
# Enable 2FA first, then generate a 16-char app password for "Mail".
NOTIFICATION_EMAIL = "vickomela36@gmail.com"
GMAIL_SENDER       = ""   # e.g. "yourname@gmail.com"
GMAIL_APP_PASSWORD = ""   # 16-char app password (no spaces)

# ── Notion ────────────────────────────────────────────────────────────────────
# Create an integration at https://www.notion.so/my-integrations and share
# the "Memecoin Buy Signals" database with it.
NOTION_TOKEN       = ""   # "secret_..."
NOTION_DATABASE_ID = "29d22a95-7503-40b9-9255-6757039bd87d"

# ── Scheduler ────────────────────────────────────────────────────────────────
CHECK_INTERVAL_HOURS = 1

# ── Signal thresholds ─────────────────────────────────────────────────────────
BUY_SIGNAL_1H_CHANGE_MIN    = 5.0     # minimum 1h price change %
BUY_SIGNAL_VOLUME_24H_MIN   = 100_000 # minimum 24h volume (USD)
BUY_SIGNAL_LIQUIDITY_MIN    = 50_000  # minimum liquidity (USD)
BUY_SIGNAL_BUY_PRESSURE_MIN = 0.60   # minimum buy / (buy+sell) ratio (last 1h)
