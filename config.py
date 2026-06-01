import os

# Tokens to track (CoinGecko IDs)
TRACKED_TOKENS = [
    "dogecoin",
    "shiba-inu",
    "pepe",
    "floki",
    "bonk",
    "dogwifcoin",
]

# Signal thresholds
BUY_VOLUME_SPIKE_MULTIPLIER = 2.0   # volume must be 2x the 7-day average
BUY_PRICE_CHANGE_MIN_PCT = 5.0       # at least +5% in 24h
BUY_MARKET_CAP_MAX_USD = 500_000_000 # cap at $500M for "micro/small cap" focus

# Notification settings
ALERT_EMAIL = "vickomela36@gmail.com"

# Loaded from environment / GitHub Actions secrets
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "b3f3ecc7fa7e4772bb765b0f32274087")
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")
