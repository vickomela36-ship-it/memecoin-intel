import os
from dotenv import load_dotenv

load_dotenv()

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "ec3ba050-a06d-40c2-a92e-a87b51ceb459"

# Gmail SMTP (use a Google App Password, not your account password)
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = "vickomela36@gmail.com"

# Optional: comma-separated token addresses to watch.
# Leave empty to auto-pull DexScreener trending/boosted tokens.
WATCH_LIST: list[str] = [
    addr.strip()
    for addr in os.getenv("WATCH_LIST", "").split(",")
    if addr.strip()
]

# Signal thresholds — tune these to taste
SIGNAL_CONFIG = {
    "min_price_change_1h_pct": 5.0,   # at least +5% in the last 1 h
    "min_volume_24h_usd": 50_000,      # at least $50 k 24-h volume
    "min_liquidity_usd": 10_000,       # at least $10 k liquidity
    "min_vol_liq_ratio": 0.3,          # volume >= 30 % of pool liquidity
}
