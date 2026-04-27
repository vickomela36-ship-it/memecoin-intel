import os
from dotenv import load_dotenv

load_dotenv()

# Email
GMAIL_SENDER       = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL        = "vickomela36@gmail.com"

# Notion — uses the existing "Memecoin Buy Signals" database
NOTION_TOKEN       = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "07d27f13-d540-461f-be2c-131eedcbde6a"

# DexScreener
DEXSCREENER_BASE = "https://api.dexscreener.com"

# Signal filter thresholds (tune as needed)
TARGET_CHAINS        = ["solana"]
MIN_LIQUIDITY_USD    = 50_000
MIN_VOLUME_24H_USD   = 100_000
MIN_PRICE_CHANGE_1H  = 5.0   # minimum +5 % in last hour to trigger buy
MAX_TOKENS_PER_RUN   = 50    # cap on tokens evaluated per cycle
