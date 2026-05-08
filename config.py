import os

# Solana pair addresses to monitor (from DexScreener URLs).
# Leave empty to auto-track top boosted/trending tokens on DexScreener.
WATCHED_PAIRS: list[str] = []

# --- Signal thresholds ---
PRICE_CHANGE_MIN_PCT = 15.0   # min 24h price gain % to trigger buy
VOL_LIQ_RATIO_MIN = 2.0       # min volume/liquidity ratio
MIN_LIQUIDITY_USD = 30_000    # ignore pairs below this liquidity

# --- Email ---
ALERT_EMAIL = "vickomela36@gmail.com"
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "vickomela36@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # Gmail App Password

# --- Notion ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
# "Memecoin Buy Signals" database (data source id)
NOTION_DATABASE_ID = "b69604b4-b942-4e4b-887a-1a138ccb64ff"
