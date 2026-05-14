import os
from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "vickomela36@gmail.com")
GMAIL_RECIPIENT = os.environ.get("GMAIL_RECIPIENT", "vickomela36@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "685b3530321a4a7ea5af6553774f29b0")

# Comma-separated Solana pair addresses to monitor (from DexScreener)
_watchlist_raw = os.environ.get("WATCHLIST", "")
WATCHLIST: list[str] = [a.strip() for a in _watchlist_raw.split(",") if a.strip()]

# Thresholds for a "buy now" signal
BUY_MIN_VOLUME_24H: float = float(os.environ.get("BUY_MIN_VOLUME_24H", "10000"))
BUY_MIN_LIQUIDITY: float = float(os.environ.get("BUY_MIN_LIQUIDITY", "5000"))
BUY_MIN_PRICE_CHANGE_24H: float = float(os.environ.get("BUY_MIN_PRICE_CHANGE_24H", "10"))
