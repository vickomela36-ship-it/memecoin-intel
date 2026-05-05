import os

# ── Email (Gmail SMTP) ────────────────────────────────────────────────────────
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")           # your Gmail address
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "") # Gmail App Password
EMAIL_RECIPIENT = "vickomela36@gmail.com"

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "9ef4b2232d1a41649c867a47f8b4350f"

# ── CoinGecko (optional – improves rate limits on paid plans) ─────────────────
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# ── Wallet (reserved for future on-chain features) ────────────────────────────
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# ── Memecoins to track (CoinGecko IDs) ───────────────────────────────────────
TRACKED_COINS = [
    "dogecoin",
    "shiba-inu",
    "pepe",
    "floki",
    "bonk",
    "dogwifcoin",
    "book-of-meme",
    "cat-in-a-dogs-world",
]

# ── Signal thresholds ─────────────────────────────────────────────────────────
BUY_MIN_CHANGE_24H = 5.0        # minimum 24h % gain
BUY_MAX_CHANGE_24H = 45.0       # cap – above this is likely overextended
BUY_MIN_VOL_TO_MCAP = 0.15      # volume/market-cap ratio floor for buy
SELL_CHANGE_24H = 50.0          # 24h gain above this → sell (take profit)
