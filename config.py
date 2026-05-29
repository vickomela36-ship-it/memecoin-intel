import os

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "9797d64fab024044aa004af806bd6c51"

# ── Gmail SMTP ────────────────────────────────────────────────────────────────
GMAIL_USER = os.environ.get("GMAIL_USER", "")          # sender address
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL_TO = "vickomela36@gmail.com"

# ── Signal thresholds ─────────────────────────────────────────────────────────
BUY_SIGNAL_MIN_SCORE = 3          # criteria needed to trigger "buy now"
MIN_LIQUIDITY_USD = 25_000        # ignore illiquid pairs
MAX_MARKET_CAP_USD = 10_000_000   # focus on low-cap gems
MIN_PRICE_CHANGE_1H = 5.0         # % gain in last hour
MIN_PRICE_CHANGE_6H = 10.0        # % gain in last 6 hours
MIN_PRICE_CHANGE_24H = 20.0       # % gain in last 24 hours
MIN_VOLUME_24H_USD = 50_000       # minimum daily volume
VOLUME_MCAP_RATIO_MIN = 0.5       # volume / mcap ratio floor (activity check)

# ── Watchlist ─────────────────────────────────────────────────────────────────
# Populate with Solana token mint addresses or other chain token addresses.
# Format: {"symbol": "TOKEN", "address": "<contract>", "chain": "solana"}
WATCHLIST: list[dict] = [
    # Examples — replace with real token addresses:
    # {"symbol": "WIF",   "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "chain": "solana"},
    # {"symbol": "BONK",  "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "chain": "solana"},
]

# ── DexScreener ───────────────────────────────────────────────────────────────
DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search?q={}"

# ── Trending scan (run when watchlist is empty) ───────────────────────────────
# DexScreener trending endpoint used as fallback
DEXSCREENER_TRENDING_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
TRENDING_CHAINS = {"solana", "ethereum", "base", "bsc"}
TRENDING_SCAN_LIMIT = 30          # how many trending tokens to evaluate
